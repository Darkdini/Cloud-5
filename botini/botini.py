#!/usr/bin/env python3
"""
botini — умный мульти-пара грид-раннер для Bybit (по умолчанию TESTNET).

Что делает по шагам:
  1. АНАЛИЗ. Скачивает историю каждой пары-кандидата и на нескольких
     отрезках (30/90/120 дней) оценивает, годится ли она для сетки.
     Оценка идёт по ХУДШЕМУ отрезку — защита от подгонки под удачу.
  2. ОТБОР. Берёт несколько лучших пар. Заведомо убыточные не торгует.
  3. ТОРГОВЛЯ. Ведёт выбранные пары параллельно (каждая — свой поток),
     делит бюджет между ними, размер ордера не ниже минимума биржи.
  4. НАБЛЮДЕНИЕ. Всё в одном терминале (каждая строка помечена парой),
     плюс панель по паре на портах 8899, 8900, 8901…
  5. ЗАЩИТА. Портфельный стоп по общей просадке — распродажа всех пар.

Запуск:            python botini.py
Быстрый старт без анализа (дефолтные параметры): python botini.py --skip-analysis
Остановка:         Ctrl+C  (чисто отменит ордера и сохранит состояние)
"""

import argparse
import logging
import os
import signal
import sys
import threading
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "bot"))
sys.path.insert(0, str(ROOT / "lab"))

# ================= НАСТРОЙКИ (правь тут) =================
# Реальный бюджет ~1500 ₽ ≈ 15 USDT (1 USDT ≈ 90–100 ₽). При минимуме
# ордера 5 USDT это ~3 ордера — значит ОДНА пара с сеткой ~3 уровня.
# Хочешь больше пар — увеличивай TOTAL_BUDGET: на каждую пару нужно
# минимум ~3×5 = 15 USDT, иначе сетке не из чего строиться.
TESTNET            = True                 # тренируемся на виртуальных деньгах
TOTAL_BUDGET       = Decimal("15")        # всего USDT (≈1500 ₽)
CANDIDATES         = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
MAX_PAIRS          = 1                     # на 15 USDT реально только одна пара
ORDER_MIN_USDT     = Decimal("5")         # минимум ордера (~500 ₽; 50 ₽ биржа не примет)
ANALYZE_DAYS       = 120                  # глубина истории для анализа
PERIODS            = [30, 90, 120]        # отрезки проверки на устойчивость
PORTFOLIO_DD_STOP  = Decimal("15")        # общий стоп по просадке портфеля, %
POLL_SEC           = 3                    # опрос биржи (почти реальное время)
INTERVAL_MIN       = 5                    # минут в свече для анализа
# ========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(ROOT / "botini.log", encoding="utf-8")],
    force=True,
)
log = logging.getLogger("botini")

# импорт рабочих модулей ПОСЛЕ настройки логов
import backtest as bt                       # noqa: E402
from bot import GridBot                      # noqa: E402
from exchange import Exchange                # noqa: E402
from notifier import Notifier                # noqa: E402
from dotenv import load_dotenv               # noqa: E402


# ------------------------------------------------- анализ

def _slice(klines, days):
    need = days * (1440 // INTERVAL_MIN)
    return klines[-need:] if len(klines) > need else klines


def analyze(symbol: str, budget_guess: Decimal):
    """Перебор параметров сетки по нескольким отрезкам. Возвращает лучшую
    по устойчивости комбинацию или None, если данных нет."""
    try:
        kl = bt.download_klines(symbol, str(INTERVAL_MIN), ANALYZE_DAYS)
    except Exception as e:
        log.warning("[%s] история не скачалась: %s", symbol, e)
        return None
    if len(kl) < 500:
        log.warning("[%s] мало данных (%d свечей) — пропуск", symbol, len(kl))
        return None

    best = None
    for rng in (3.0, 5.0, 7.0, 10.0):
        for lv in (8, 12, 16, 20):
            worst, dd = 1e9, 0.0
            for days in PERIODS:
                res, _ = bt.simulate(_slice(kl, days), float(budget_guess),
                                     rng, lv, 3.0, True, symbol, days)
                worst = min(worst, res.net_pct)
                dd = max(dd, res.max_drawdown_pct)
            if best is None or worst > best["worst"]:
                best = {"symbol": symbol, "range": rng, "levels": lv,
                        "worst": worst, "dd": dd}
    return best


# ------------------------------------------------- портфель

def portfolio_equity(bots):
    """Общий депозит по всему счёту: USDT (общий) + монеты всех пар по цене."""
    usdt = None
    coins_value = Decimal("0")
    for b in bots:
        u, base = b.ex.balances()
        if usdt is None:
            usdt = u
        p = b.ex.price()
        if p is None:
            return None
        coins_value += base * p
    return (usdt or Decimal("0")) + coins_value


def portfolio_guard(bots):
    def loop():
        initial = None
        while any(b.running for b in bots):
            time.sleep(30)
            eq = portfolio_equity(bots)
            if eq is None:
                continue
            if initial is None:
                initial = eq
                log.info("📦 Стартовый депозит портфеля: %.2f USDT", float(eq))
                continue
            dd = (initial - eq) / initial * 100 if initial > 0 else Decimal("0")
            total_profit = sum(float(b.profit) for b in bots)
            log.info("📦 Портфель: депозит %.2f USDT | профит суммарно +%.4f | просадка %.2f%%",
                     float(eq), total_profit, float(dd))
            if dd >= PORTFOLIO_DD_STOP:
                log.error("🛑 ПОРТФЕЛЬНАЯ ПРОСАДКА %.1f%% ≥ %s%% — стоп всех пар и распродажа!",
                          float(dd), PORTFOLIO_DD_STOP)
                for b in bots:
                    try:
                        b.sell_everything()
                    finally:
                        b.running = False
                break
    threading.Thread(target=loop, name="portfolio", daemon=True).start()


# ------------------------------------------------- запуск

def base_config():
    return dict(
        testnet=TESTNET, rebuild_on_breakout_up=True, breakout_confirm_polls=3,
        stop_action="stop", rebuild_cooldown_min=30, stop_loss_extra_pct=3.0,
        max_drawdown_pct=0,          # просадкой рулит портфельный стоп botini
        volatility_max_pct=1.2, poll_interval_sec=POLL_SEC, report_hour=21,
        heartbeat_sec=15, candle_log_sec=60, candle_interval=str(INTERVAL_MIN),
        web_enabled=True,
    )


def main():
    ap = argparse.ArgumentParser(description="botini — умный мульти-пара грид")
    ap.add_argument("--skip-analysis", action="store_true",
                    help="не анализировать, взять первые пары с дефолтными параметрами")
    a = ap.parse_args()

    load_dotenv(ROOT / "bot" / ".env")
    load_dotenv(ROOT / ".env")
    key, secret = os.getenv("BYBIT_API_KEY"), os.getenv("BYBIT_API_SECRET")
    if not key or not secret:
        log.error("Нет ключей Bybit. Впиши их в bot/.env (BYBIT_API_KEY / BYBIT_API_SECRET).")
        sys.exit(1)

    mode = "TESTNET (виртуальные деньги)" if TESTNET else "⚠️ РЕАЛЬНЫЕ ДЕНЬГИ ⚠️"
    log.info("=== botini · %s · бюджет %s USDT ===", mode, TOTAL_BUDGET)

    # --- отбор пар ---
    if a.skip_analysis:
        log.info("Анализ пропущен (--skip-analysis): беру %d пар с дефолтом ±5%% x10", MAX_PAIRS)
        chosen = [{"symbol": s, "range": 5.0, "levels": 10, "worst": 0.0, "dd": 0.0}
                  for s in CANDIDATES[:MAX_PAIRS]]
    else:
        log.info("Анализирую %d пар на истории (это займёт минуту)…", len(CANDIDATES))
        guess = TOTAL_BUDGET / MAX_PAIRS
        scored = []
        for sym in CANDIDATES:
            r = analyze(sym, guess)
            if r:
                verdict = "годится" if r["worst"] > 0 else "рискованно"
                log.info("[%s] ±%s%% x%d | худший отрезок %+.2f%% | просадка ≤%.1f%% → %s",
                         sym, r["range"], r["levels"], r["worst"], r["dd"], verdict)
                scored.append(r)
        if not scored:
            log.error("Анализ без данных (нет сети?). Запусти с --skip-analysis, если уверен.")
            sys.exit(1)
        scored.sort(key=lambda x: x["worst"], reverse=True)
        chosen = [s for s in scored if s["worst"] > -5][:MAX_PAIRS]
        if not chosen:
            log.error("Ни одна пара не прошла: рынок сейчас не для грида. Не торгую (это защита).")
            sys.exit(0)

    budget_each = (TOTAL_BUDGET / len(chosen)).quantize(Decimal("0.01"))
    log.info("Отобрано пар: %s | бюджет на пару: %s USDT",
             ", ".join(c["symbol"] for c in chosen), budget_each)

    # --- запуск воркеров ---
    notifier = Notifier()
    run_dir = ROOT / "run"
    run_dir.mkdir(exist_ok=True)
    bots, threads, port = [], [], 8899
    for c in chosen:
        cfg = base_config()
        cfg["grid_range_pct"] = c["range"]
        cfg["grid_levels"] = c["levels"]
        cfg["web_port"] = port
        # уровней не больше, чем позволяет минимум ордера биржи
        while cfg["grid_levels"] > 1 and budget_each / cfg["grid_levels"] < ORDER_MIN_USDT:
            cfg["grid_levels"] -= 1
        try:
            ex = Exchange(key, secret, TESTNET, c["symbol"])
        except Exception as e:
            log.error("[%s] не удалось подключить пару: %s — пропуск", c["symbol"], e)
            continue
        bot = GridBot(cfg, c["symbol"], budget_each, ex, notifier,
                      state_file=str(run_dir / f"state_{c['symbol']}.json"))
        t = threading.Thread(target=bot.run, name=c["symbol"], daemon=False)
        bots.append(bot)
        threads.append(t)
        t.start()
        log.info("[%s] запущен · ±%s%% x%d · панель http://localhost:%d",
                 c["symbol"], cfg["grid_range_pct"], cfg["grid_levels"], port)
        port += 1
        time.sleep(1)

    if not bots:
        log.error("Не удалось запустить ни одной пары.")
        sys.exit(1)

    portfolio_guard(bots)

    # --- чистая остановка по Ctrl+C ---
    def shutdown(*_):
        log.info("⏹ Останавливаю все пары: отменяю ордера, сохраняю состояние…")
        for b in bots:
            b.stop_requested = True
    signal.signal(signal.SIGINT, shutdown)

    for t in threads:
        t.join()
    log.info("botini остановлен. Состояние в папке run/ — при следующем запуске подхватится.")


if __name__ == "__main__":
    main()
