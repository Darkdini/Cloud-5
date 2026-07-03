"""
Bybit Grid Bot v2 — автономный сеточный бот для спота.

Что умеет сверх базовой сетки:
  - автоперестройка при уходе цены выше сетки
  - лимит просадки депозита (полная остановка)
  - фильтр волатильности (не строит сетку в шторм)
  - живой вывод в консоль Termux + панель на http://localhost:8899
  - восстановление после перезапуска из state.json

Запуск:      python bot.py         (или run.bat / run.sh — с авторестартом)
Остановка:   Ctrl+C
"""

import json
import logging
import os
import signal
import sys
import time
from collections import deque
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import yaml
from dotenv import load_dotenv

import webui
from exchange import Exchange, d, round_step
from notifier import Notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler("bot.log", encoding="utf-8")],
)
log = logging.getLogger("gridbot")


class GridBot:
    def __init__(self, cfg=None, symbol=None, budget=None, exchange=None,
                 notifier=None, state_file="state.json"):
        """Standalone: GridBot() — читает config.yaml сам, как раньше.
        Мульти-пара (botini): передай cfg/symbol/budget/exchange/notifier/state_file."""
        if cfg is None:
            with open("config.yaml", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        self.cfg = cfg
        self.symbol = symbol or cfg["symbol"]
        self.budget = d(budget if budget is not None else cfg["budget_usdt"])
        self.state_file = Path(state_file)
        self.testnet = bool(cfg.get("testnet", True))

        load_dotenv()
        if exchange is None:
            key = os.getenv("BYBIT_API_KEY")
            secret = os.getenv("BYBIT_API_SECRET")
            if not key or not secret:
                log.error("Нет ключей Bybit. Скопируй .env.example в .env и заполни (README, шаг 2).")
                sys.exit(1)
            exchange = Exchange(key, secret, self.testnet, self.symbol)
        self.ex = exchange
        self.tg = notifier or Notifier()   # Telegram убран: всё видно в консоли и на localhost

        self.orders: dict = {}          # orderId -> {side, level, price, qty}
        self.levels: list[Decimal] = []
        self.profit = Decimal("0")
        self.trades = 0
        self.initial_equity: Decimal | None = None
        self.running = True
        self.paused_by_volatility = False
        self.breakout_count = 0
        self.last_report_date = None

        # для веб-панели
        self.price_cache: Decimal | None = None
        self.events = deque(maxlen=60)
        self.history = deque(maxlen=2880)   # ~4 часа при опросе раз в 5 сек
        self.stop_requested = False

        # таймеры наглядного вывода в консоль
        self._last_hb = 0.0
        self._last_candle = 0.0

    def event(self, text: str):
        """Строка в ленту событий веб-панели."""
        self.events.appendleft(f"{datetime.now().strftime('%H:%M:%S')}  {text}")

    def _heartbeat(self, price: Decimal):
        """Живой вывод в консоль Termux: пульс (цена/ордера/профит/связь) и
        свежая свеча O/H/L/C. Частота — heartbeat_sec / candle_log_sec в конфиге."""
        now = time.time()
        hb = int(self.cfg.get("heartbeat_sec", 15))
        if hb and now - self._last_hb >= hb:
            self._last_hb = now
            log.info("⏱ цена %s | ордеров %d | профит +%s USDT | %s",
                     price, len(self.orders), self.profit.quantize(d("0.0001")),
                     "🟢 связь" if self.ex.connected else "🔴 нет связи")
        clog = int(self.cfg.get("candle_log_sec", 60))
        if clog and now - self._last_candle >= clog:
            self._last_candle = now
            interval = str(self.cfg.get("candle_interval", "5"))
            k = self.ex.last_kline(interval)
            if k:
                o, h, l, c = k
                mark = "🟩 рост" if c >= o else "🟥 спад"
                log.info("🕯 свеча %sм  O:%s  H:%s  L:%s  C:%s  %s",
                         interval, o, h, l, c, mark)

    # ================= состояние =================

    def save_state(self):
        self.state_file.write_text(json.dumps({
            "symbol": self.symbol,
            "orders": self.orders,
            "levels": [str(x) for x in self.levels],
            "profit": str(self.profit),
            "trades": self.trades,
            "initial_equity": str(self.initial_equity) if self.initial_equity else None,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def try_restore(self) -> bool:
        if not self.state_file.exists():
            return False
        try:
            s = json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return False
        if s.get("symbol") != self.symbol or not s.get("levels"):
            return False

        self.orders = s.get("orders", {})
        self.levels = [d(x) for x in s["levels"]]
        self.profit = d(s.get("profit", "0"))
        self.trades = int(s.get("trades", 0))
        if s.get("initial_equity"):
            self.initial_equity = d(s["initial_equity"])
        self._recalc_bounds()

        # сверка с биржей: что исполнилось, пока бот был выключен
        if self.reconcile_orders() is None:
            return False
        alive = len(self.orders)
        log.info("Восстановлено из state.json: %d активных ордеров, профит %s USDT",
                 alive, self.profit)
        self.tg.send(f"♻️ Бот перезапущен, восстановлено {alive} ордеров. "
                     f"Профит всего: +{self.profit:.4f} USDT")
        return alive > 0

    def _recalc_bounds(self):
        self.lower = self.levels[0]
        self.upper = self.levels[-1]
        self.stop_price = self.lower * (1 - d(self.cfg.get("stop_loss_extra_pct", 0)) / 100)

    # ================= ордера =================

    def _place_tracked(self, side: str, price: Decimal, qty: Decimal,
                       level: int, retries: int = 3) -> str | None:
        """Ставит лимит и берёт его в учёт. При отказе — ретраит и предупреждает,
        чтобы не оставить сетку с молчаливой дырой (баг: потерянный ордер)."""
        for att in range(retries):
            oid = self.ex.place_limit(side, price, qty)
            if oid:
                self.orders[oid] = {"side": side, "level": level,
                                    "price": str(price), "qty": str(qty)}
                return oid
            log.warning("Не выставился %s %s @ %s — попытка %d/%d",
                        side, qty, price, att + 1, retries)
            time.sleep(1.5)
        self.tg.send(f"⚠️ Не смог выставить {side} {qty} @ {price}. "
                     f"Проверь бота — в сетке возможна дыра.")
        self.event(f"⚠️ Ошибка постановки {side} @ {price}")
        return None

    # ================= сетка =================

    def volatility_ok(self) -> bool:
        vmax = d(self.cfg.get("volatility_max_pct", 0))
        if vmax == 0:
            return True
        v = self.ex.volatility_pct()
        if v is None:
            return True
        ok = v <= vmax
        if not ok and not self.paused_by_volatility:
            log.warning("Волатильность %.2f%% выше порога %.2f%% — жду успокоения", v, vmax)
            self.tg.send(f"🌪 Волатильность {v:.2f}% выше порога. Новая сетка отложена.")
            self.paused_by_volatility = True
        if ok and self.paused_by_volatility:
            self.paused_by_volatility = False
            log.info("Волатильность в норме (%.2f%%)", v)
        return ok

    def build_grid(self) -> bool:
        if not self.volatility_ok():
            return False
        price = self.ex.price()
        if price is None:
            return False

        rng = d(self.cfg["grid_range_pct"]) / 100
        n = int(self.cfg["grid_levels"])
        lo, hi = price * (1 - rng), price * (1 + rng)
        step = (hi - lo) / (n + 1)
        self.levels = [round_step(lo + step * i, self.ex.tick_size) for i in range(n + 2)]
        self._recalc_bounds()

        if self.initial_equity is None:
            self.initial_equity = self.ex.equity()

        per_level = self.budget / n
        placed = 0
        for i, lvl in enumerate(self.levels):
            if lvl >= price:
                continue
            qty = round_step(per_level / lvl, self.ex.qty_step)
            if qty < self.ex.min_qty or qty * lvl < self.ex.min_amt:
                log.warning("Уровень %s пропущен: меньше минимума биржи", lvl)
                continue
            if self._place_tracked("Buy", lvl, qty, i):
                placed += 1
            time.sleep(0.15)

        if placed == 0:
            log.error("Ни одного ордера. Увеличь budget_usdt или уменьши grid_levels.")
            return False
        log.info("Сетка: %s…%s, %d покупок, цена %s", self.lower, self.upper, placed, price)
        self.event(f"📊 Сетка {self.lower}–{self.upper}, {placed} покупок")
        self.tg.send(f"📊 Сетка построена: {self.symbol}\n"
                     f"Диапазон {self.lower}–{self.upper}\nОрдеров: {placed}")
        self.save_state()
        return True

    def rebuild_grid(self, reason: str):
        log.info("Перестройка сетки: %s", reason)
        self.ex.cancel_all()
        self.orders.clear()
        self.breakout_count = 0
        # ждём подходящей волатильности сколько потребуется
        while self.running and not self.build_grid():
            time.sleep(60)

    # ================= события =================

    def on_filled(self, o: dict):
        level = int(o["level"])
        price, qty = d(o["price"]), d(o["qty"])

        if o["side"] == "Buy":
            sell_level = level + 1
            if sell_level < len(self.levels):
                sp = self.levels[sell_level]
                self._place_tracked("Sell", sp, qty, sell_level)
                log.info(">>> КУПЛЕНО L%d @ %s -> продажа @ %s", level, price, sp)
                self.event(f"🟢 Куплено @ {price} → продажа @ {sp}")
            else:
                log.warning("Куплено на верхнем уровне L%d @ %s — парной продажи нет "
                            "(монета без выхода до перестройки сетки)", level, price)
                self.event(f"🟡 Куплено @ {price} — верхний уровень, продажи нет")
        else:
            buy_level = level - 1
            bp = self.levels[buy_level]
            pair_profit = (price - bp) * qty
            self.profit += pair_profit
            self.trades += 1
            log.info(">>> ПРОДАНО L%d @ %s | +%s USDT | всего +%s (%d сделок)",
                     level, price, pair_profit.quantize(d("0.0001")),
                     self.profit.quantize(d("0.0001")), self.trades)
            self.event(f"✅ Сделка закрыта: +{pair_profit:.4f} USDT")
            self.tg.send(f"✅ Сделка закрыта: +{pair_profit:.4f} USDT\n"
                         f"Всего: +{self.profit:.4f} USDT ({self.trades} сделок)")
            self._place_tracked("Buy", bp, qty, buy_level)

    def sell_everything(self):
        self.ex.cancel_all()
        self.orders.clear()
        _, base = self.ex.balances()
        qty = round_step(base, self.ex.qty_step)
        if qty >= self.ex.min_qty:
            self.ex.market_sell(qty)
            log.info("Распродано по рынку: %s %s", qty, self.ex.base)
            self.event(f"🛑 Распродано по рынку: {qty} {self.ex.base}")

    # статусы, при которых ордер точно неактивен и НЕ исполнен
    _DEAD_STATUSES = ("Cancelled", "Canceled", "Rejected",
                      "Deactivated", "PartiallyFilledCanceled")

    def reconcile_orders(self):
        """Сверка учтённых ордеров с биржей.
        Возвращает True, если что-то обработали, False — если нет,
        None — если биржа недоступна (тогда НИЧЕГО не трогаем и повторим позже).

        Ключевой момент: ордер снимается с учёта только при определённом
        статусе. При сбое связи статус неизвестен — ордер остаётся, иначе
        реальное исполнение потерялось бы и монета повисла бы вне учёта."""
        open_ids = self.ex.open_order_ids()
        if open_ids is None:
            return None
        gone = [oid for oid in list(self.orders) if oid not in open_ids]
        changed = False
        for oid in gone:
            status = self.ex.order_status(oid)
            if status == "Filled":
                o = self.orders.pop(oid, None)
                if o:
                    self.on_filled(o)
                    changed = True
            elif status in self._DEAD_STATUSES:
                self.orders.pop(oid, None)
                changed = True
                log.info("Ордер %s… снят с учёта: статус %s", oid[:8], status)
            else:
                log.debug("Ордер %s… пропал, статус '%s' — оставляю на повтор",
                          oid[:8], status)
        return changed

    # ================= защиты =================

    def check_drawdown(self) -> bool:
        limit = d(self.cfg.get("max_drawdown_pct", 0))
        if limit == 0 or self.initial_equity in (None, Decimal("0")):
            return False
        eq = self.ex.equity()
        if eq is None:
            return False
        dd = (self.initial_equity - eq) / self.initial_equity * 100
        if dd >= limit:
            msg = (f"🛑 ЛИМИТ ПРОСАДКИ {limit}% ДОСТИГНУТ ({dd:.1f}%).\n"
                   f"Депозит: {eq:.2f} из {self.initial_equity:.2f} USDT.\n"
                   f"Всё распродано, бот ОСТАНОВЛЕН. Нужно твоё решение.")
            log.error(msg)
            self.tg.send(msg)
            self.sell_everything()
            self.running = False
            return True
        return False

    def check_price_bounds(self, price: Decimal):
        # пробой вверх
        if self.cfg.get("rebuild_on_breakout_up", True) and price > self.upper:
            self.breakout_count += 1
            need = int(self.cfg.get("breakout_confirm_polls", 3))
            if self.breakout_count >= need:
                self.tg.send(f"🚀 Цена ушла выше сетки ({price}). Перестраиваю выше.")
                self.rebuild_grid("пробой вверх")
            return
        self.breakout_count = 0

        # пробой вниз
        if d(self.cfg.get("stop_loss_extra_pct", 0)) > 0 and price < self.stop_price:
            self.tg.send(f"🛑 Цена пробила стоп ({price} < {self.stop_price}). Распродаю.")
            log.warning("Аварийный стоп по цене")
            self.sell_everything()
            if self.cfg.get("stop_action", "stop") == "rebuild":
                cd = int(self.cfg.get("rebuild_cooldown_min", 30))
                self.tg.send(f"⏸ Пауза {cd} мин, затем новая сетка ниже.")
                for _ in range(cd * 6):
                    if not self.running:
                        return
                    time.sleep(10)
                self.rebuild_grid("после стопа")
            else:
                self.tg.send("Бот остановлен. Реши сам: перезапустить или переждать рынок.")
                self.running = False

    # ================= отчёт =================

    def maybe_daily_report(self):
        now = datetime.now()
        if now.hour != int(self.cfg.get("report_hour", 21)):
            return
        if self.last_report_date == now.date():
            return
        self.last_report_date = now.date()
        eq = self.ex.equity()
        eq_txt = f"{eq:.2f}" if eq is not None else "?"
        self.tg.send(f"📈 Дневной отчёт {self.symbol}\n"
                     f"Профит всего: +{self.profit:.4f} USDT\n"
                     f"Закрыто сделок: {self.trades}\n"
                     f"Депозит: {eq_txt} USDT\n"
                     f"Активных ордеров: {len(self.orders)}")

    # ================= главный цикл =================

    def run(self):
        mode = "TESTNET (виртуальные деньги)" if self.testnet else "⚠️ РЕАЛЬНЫЕ ДЕНЬГИ ⚠️"
        log.info("Режим: %s | бюджет %s USDT", mode, self.budget)
        self.tg.send(f"🤖 Grid Bot запущен | {self.symbol} | {mode}")

        if self.cfg.get("web_enabled", True):
            port = int(self.cfg.get("web_port", 8899))
            try:
                webui.start(self, port)
                log.info("Веб-панель: http://localhost:%d  <- открой в браузере", port)
                self.event(f"Панель запущена: http://localhost:{port}")
            except OSError as e:
                log.warning("Панель не запустилась (порт %d занят?): %s", port, e)
        if not self.testnet:
            log.warning("Боевой режим! 10 секунд на Ctrl+C...")
            time.sleep(10)

        if not self.try_restore():
            wait = min(int(self.cfg.get("poll_interval_sec", 5)) * 4, 60)
            while self.running and not self.stop_requested and not self.build_grid():
                time.sleep(wait)
            if self.stop_requested:
                self.running = False
                return

        poll = int(self.cfg.get("poll_interval_sec", 5))
        while self.running:
            time.sleep(poll)
            price = self.ex.price()
            if price is None:
                continue
            self.price_cache = price
            self.history.append((int(time.time()), float(self.profit)))

            if self.stop_requested:
                log.info("Остановка с веб-панели")
                self.event("⏹ Остановка кнопкой на панели")
                self.tg.send("⏹ Бот остановлен кнопкой на веб-панели")
                self.ex.cancel_all()
                self.orders.clear()
                self.save_state()
                self.running = False
                break

            self._heartbeat(price)

            if self.check_drawdown():
                break
            self.check_price_bounds(price)
            if not self.running:
                break

            changed = self.reconcile_orders()
            if changed is None:
                continue          # биржа недоступна — ждём, ничего не трогаем
            if changed:
                self.save_state()

            self.maybe_daily_report()

        log.info("Остановлен. Итог: +%s USDT, сделок: %d", self.profit, self.trades)


def main():
    bot = GridBot()

    def on_sigint(sig, frame):
        print()
        ans = input("Отменить все ордера перед выходом? [y/N]: ").strip().lower()
        if ans == "y":
            bot.ex.cancel_all()
            bot.orders.clear()
            bot.save_state()
        bot.tg.send("⏹ Бот выключен вручную (Ctrl+C)")
        sys.exit(0)

    signal.signal(signal.SIGINT, on_sigint)

    try:
        bot.run()
    except Exception as e:
        log.exception("Критическая ошибка: %s", e)
        bot.tg.send(f"💥 Бот упал с ошибкой: {e}\nWatchdog перезапустит, ордера восстановятся.")
        raise


if __name__ == "__main__":
    main()
