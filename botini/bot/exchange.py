"""Обёртка над Bybit API: ретраи, лимиты инструмента, удобные методы."""

import logging
import time
from decimal import Decimal, ROUND_DOWN

from pybit.unified_trading import HTTP

log = logging.getLogger("gridbot")


def d(x) -> Decimal:
    return Decimal(str(x))


def round_step(value: Decimal, step: Decimal) -> Decimal:
    if step == 0:
        return value
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


class Exchange:
    def __init__(self, api_key: str, api_secret: str, testnet: bool, symbol: str):
        self.symbol = symbol
        self.base = symbol.replace("USDT", "")
        self.connected = True   # состояние связи с биржей (для наглядных логов)
        net = "TESTNET (виртуальные деньги)" if testnet else "MAINNET (реальные)"
        log.info("🔌 Подключаюсь к Bybit · %s · пара %s", net, symbol)
        self.session = HTTP(testnet=testnet, api_key=api_key, api_secret=api_secret)
        self._load_limits()
        log.info("🟢 Подключено к бирже, инструмент загружен")

    def _api(self, fn, **kwargs):
        for attempt in range(5):
            try:
                resp = fn(**kwargs)
                if resp.get("retCode") == 0:
                    if not self.connected:
                        self.connected = True
                        log.info("🟢 Связь с биржей восстановлена")
                    return resp["result"]
                log.warning("API retCode=%s: %s", resp.get("retCode"), resp.get("retMsg"))
                return None
            except Exception as e:
                log.warning("Сбой сети (%s), попытка %d/5", e, attempt + 1)
                time.sleep(2 * (attempt + 1))
        if self.connected:
            self.connected = False
            log.error("🔴 Потеря связи с биржей (%s). Повторю на следующем опросе.",
                      getattr(fn, "__name__", fn))
        return None

    def _load_limits(self):
        res = self._api(self.session.get_instruments_info,
                        category="spot", symbol=self.symbol)
        if not res or not res["list"]:
            raise RuntimeError(f"Пара {self.symbol} не найдена на споте")
        info = res["list"][0]
        self.tick_size = d(info["priceFilter"]["tickSize"])
        lf = info["lotSizeFilter"]
        self.qty_step = d(lf["basePrecision"])
        self.min_qty = d(lf.get("minOrderQty", "0"))
        self.min_amt = d(lf.get("minOrderAmt", "1"))
        log.info("Лимиты %s: tick=%s qty_step=%s min_amt=%s USDT",
                 self.symbol, self.tick_size, self.qty_step, self.min_amt)

    # ---------- рынок ----------

    def price(self) -> Decimal | None:
        res = self._api(self.session.get_tickers, category="spot", symbol=self.symbol)
        if res and res["list"]:
            return d(res["list"][0]["lastPrice"])
        return None

    def last_kline(self, interval: str = "5"):
        """Свежая свеча: (open, high, low, close). Для наглядного лога."""
        res = self._api(self.session.get_kline, category="spot",
                        symbol=self.symbol, interval=interval, limit=1)
        if res and res["list"]:
            k = res["list"][0]
            return d(k[1]), d(k[2]), d(k[3]), d(k[4])
        return None

    def volatility_pct(self) -> Decimal | None:
        """Средний размах 5-минутной свечи за последние 2 часа, в %."""
        res = self._api(self.session.get_kline, category="spot",
                        symbol=self.symbol, interval="5", limit=24)
        if not res or not res["list"]:
            return None
        total = Decimal("0")
        n = 0
        for k in res["list"]:
            high, low, close = d(k[2]), d(k[3]), d(k[4])
            if close > 0:
                total += (high - low) / close * 100
                n += 1
        return total / n if n else None

    # ---------- ордера ----------

    def place_limit(self, side: str, price: Decimal, qty: Decimal) -> str | None:
        res = self._api(self.session.place_order, category="spot",
                        symbol=self.symbol, side=side, orderType="Limit",
                        qty=str(qty), price=str(price), timeInForce="GTC")
        return res.get("orderId") if res else None

    def market_sell(self, qty: Decimal) -> bool:
        res = self._api(self.session.place_order, category="spot",
                        symbol=self.symbol, side="Sell",
                        orderType="Market", qty=str(qty))
        return res is not None

    def cancel_all(self):
        self._api(self.session.cancel_all_orders, category="spot", symbol=self.symbol)

    def open_order_ids(self) -> set[str] | None:
        res = self._api(self.session.get_open_orders, category="spot",
                        symbol=self.symbol, limit=50)
        if res is None:
            return None
        return {o["orderId"] for o in res["list"]}

    def order_status(self, order_id: str) -> str | None:
        res = self._api(self.session.get_order_history, category="spot",
                        symbol=self.symbol, orderId=order_id)
        if res and res["list"]:
            return res["list"][0]["orderStatus"]
        return None

    # ---------- баланс ----------

    def balances(self) -> tuple[Decimal, Decimal]:
        """(USDT, базовая монета)"""
        res = self._api(self.session.get_wallet_balance, accountType="UNIFIED")
        usdt = base = Decimal("0")
        if res:
            for acc in res["list"]:
                for coin in acc["coin"]:
                    if coin["coin"] == "USDT":
                        usdt = d(coin["walletBalance"] or 0)
                    elif coin["coin"] == self.base:
                        base = d(coin["walletBalance"] or 0)
        return usdt, base

    def equity(self) -> Decimal | None:
        p = self.price()
        if p is None:
            return None
        usdt, base = self.balances()
        return usdt + base * p
