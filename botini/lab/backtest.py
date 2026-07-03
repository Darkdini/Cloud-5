"""
GridLab — бэктестер сеточной стратегии на реальной истории Bybit.

Что делает:
  1. Скачивает исторические свечи с публичного API Bybit (ключи не нужны).
  2. Симулирует нашу грид-стратегию свеча за свечой: покупки/продажи,
     комиссии, стоп-лосс, перестройку сетки при пробое вверх.
  3. Считает метрики и честно сравнивает с "просто купил и держал".
  4. Режим --sweep перебирает комбинации параметров и показывает таблицу.

Примеры:
  python backtest.py --symbol BTCUSDT --days 90
  python backtest.py --symbol BTCUSDT --days 180 --range 7 --levels 15
  python backtest.py --symbol BTCUSDT --days 90 --sweep

Результат: отчёт в консоли + график equity_curve.png
"""

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests

BYBIT = "https://api.bybit.com/v5/market/kline"
FEE = 0.001  # 0.1% спот-комиссия Bybit за сторону (тейкер/мейкер базовый)
CACHE = Path("data")


# ----------------------------------------------------------- данные

def download_klines(symbol: str, interval: str, days: int) -> list:
    """Свечи [ts, open, high, low, close] от старых к новым. Кэш в data/."""
    CACHE.mkdir(exist_ok=True)
    cache_file = CACHE / f"{symbol}_{interval}m_{days}d.csv"
    if cache_file.exists():
        with open(cache_file, newline="") as f:
            rows = [[int(r[0])] + [float(x) for x in r[1:]] for r in csv.reader(f)]
        print(f"Данные из кэша: {cache_file} ({len(rows)} свечей)")
        return rows

    end = int(time.time() * 1000)
    start = end - days * 86400_000
    out = []
    cursor = end
    print(f"Скачиваю {symbol} {interval}m за {days} дней с Bybit...")
    while cursor > start:
        r = requests.get(BYBIT, params={
            "category": "spot", "symbol": symbol,
            "interval": interval, "end": cursor, "limit": 1000,
        }, timeout=15)
        data = r.json()
        if data.get("retCode") != 0:
            sys.exit(f"Ошибка API Bybit: {data.get('retMsg')}")
        rows = data["result"]["list"]  # новые -> старые
        if not rows:
            break
        for k in rows:
            ts = int(k[0])
            if ts >= start:
                out.append([ts, float(k[1]), float(k[2]), float(k[3]), float(k[4])])
        cursor = int(rows[-1][0]) - 1
        print(f"  ...{len(out)} свечей", end="\r")
        time.sleep(0.12)

    out.sort(key=lambda x: x[0])
    with open(cache_file, "w", newline="") as f:
        csv.writer(f).writerows(out)
    print(f"\nСкачано {len(out)} свечей, кэш: {cache_file}")
    return out


# ----------------------------------------------------------- симуляция

@dataclass
class Result:
    symbol: str
    days: int
    range_pct: float
    levels: int
    budget: float
    net_profit: float      # итоговый P&L с учётом комиссий и остатка монеты
    grid_profit: float     # профит закрытых пар (реализованный)
    fees_paid: float
    trades: int
    max_drawdown_pct: float
    rebuilds: int
    stops: int
    hold_profit: float     # сколько дал бы buy&hold тем же бюджетом
    final_equity: float

    @property
    def net_pct(self):
        return self.net_profit / self.budget * 100

    @property
    def hold_pct(self):
        return self.hold_profit / self.budget * 100


def simulate(klines: list, budget: float, range_pct: float, levels: int,
             stop_extra_pct: float, rebuild_up: bool,
             symbol: str = "", days: int = 0) -> tuple[Result, list]:
    cash = budget
    inventory = 0.0          # монеты на руках
    grid_profit = 0.0
    fees = 0.0
    trades = 0
    rebuilds = 0
    stops = 0
    equity_curve = []
    peak = budget
    max_dd = 0.0

    grid = None  # {"levels": [...], "buys": {lvl_i: qty}, "sells": {lvl_i: qty}}

    def build_grid(price):
        nonlocal cash, grid
        lo, hi = price * (1 - range_pct / 100), price * (1 + range_pct / 100)
        step = (hi - lo) / (levels + 1)
        lv = [lo + step * i for i in range(levels + 2)]
        per = budget / levels
        buys = {}
        for i, p in enumerate(lv):
            if p < price and cash >= per:
                buys[i] = per / p
        grid = {"levels": lv, "buys": buys, "sells": {},
                "stop": lv[0] * (1 - stop_extra_pct / 100)}

    start_price = klines[0][4]
    build_grid(start_price)

    for ts, o, high, low, close in klines:
        if grid is None:
            build_grid(close)
            rebuilds += 1

        lv = grid["levels"]

        # Продажи, которые УЖЕ висели на входе в свечу. Только они могут
        # исполниться в эту же свечу. Продажа, созданная покупкой этой же
        # свечи, ждёт следующей — иначе бэктест ловил бы полный профит уровня
        # за одну свечу, предполагая идеальный внутрисвечной порядок «вниз,
        # потом вверх», и завышал результат (и вводил в заблуждение оптимизатор).
        sells_ready = set(grid["sells"].keys())

        # исполнение покупок (цена коснулась уровня снизу)
        for i in sorted(list(grid["buys"].keys()), reverse=True):
            p = lv[i]
            if low <= p:
                qty = grid["buys"].pop(i)
                cost = qty * p
                if cash < cost:
                    continue
                cash -= cost
                fee = cost * FEE
                cash -= fee
                fees += fee
                inventory += qty
                if i + 1 < len(lv):
                    grid["sells"][i + 1] = grid["sells"].get(i + 1, 0) + qty

        # исполнение продаж (цена коснулась уровня сверху)
        for i in sorted(list(grid["sells"].keys())):
            if i not in sells_ready:
                continue          # создана этой же свечой — ждёт следующей
            p = lv[i]
            if high >= p:
                qty = grid["sells"].pop(i)
                proceeds = qty * p
                fee = proceeds * FEE
                cash += proceeds - fee
                fees += fee
                inventory -= qty
                grid_profit += qty * (p - lv[i - 1])
                trades += 1
                # вернуть покупку на уровень ниже
                grid["buys"][i - 1] = grid["buys"].get(i - 1, 0) + qty

        # стоп-лосс: пробой вниз
        if stop_extra_pct > 0 and low < grid["stop"]:
            if inventory > 0:
                proceeds = inventory * grid["stop"]
                fee = proceeds * FEE
                cash += proceeds - fee
                fees += fee
                inventory = 0.0
            stops += 1
            grid = None  # перестроимся на следующей свече (режим rebuild)
            equity_curve.append((ts, cash))
            continue

        # пробой вверх -> перестройка
        if rebuild_up and close > lv[-1]:
            # распродаём остаток по close (обычно к этому моменту почти всё продано)
            if inventory > 0:
                proceeds = inventory * close
                fee = proceeds * FEE
                cash += proceeds - fee
                fees += fee
                inventory = 0.0
            build_grid(close)
            rebuilds += 1

        eq = cash + inventory * close
        equity_curve.append((ts, eq))
        peak = max(peak, eq)
        dd = (peak - eq) / peak * 100
        max_dd = max(max_dd, dd)

    final_price = klines[-1][4]
    final_equity = cash + inventory * final_price
    hold_qty = budget / start_price * (1 - FEE)
    hold_profit = hold_qty * final_price * (1 - FEE) - budget

    return Result(
        symbol=symbol, days=days, range_pct=range_pct, levels=levels,
        budget=budget, net_profit=final_equity - budget,
        grid_profit=grid_profit, fees_paid=fees, trades=trades,
        max_drawdown_pct=max_dd, rebuilds=rebuilds, stops=stops,
        hold_profit=hold_profit, final_equity=final_equity,
    ), equity_curve


# ----------------------------------------------------------- отчёты

def print_report(r: Result):
    verdict_grid = "ПЛЮС" if r.net_profit > 0 else "МИНУС"
    print()
    print("=" * 62)
    print(f"  БЭКТЕСТ: {r.symbol} | {r.days} дней | сетка ±{r.range_pct}% × {r.levels} уровней")
    print("=" * 62)
    print(f"  Бюджет:                {r.budget:>12.2f} USDT")
    print(f"  Итог стратегии:        {r.final_equity:>12.2f} USDT")
    print(f"  Чистый результат:      {r.net_profit:>+12.2f} USDT ({r.net_pct:+.2f}%)  [{verdict_grid}]")
    print(f"  Профит закрытых пар:   {r.grid_profit:>+12.2f} USDT")
    print(f"  Комиссии:              {r.fees_paid:>12.2f} USDT")
    print(f"  Закрытых сделок:       {r.trades:>12d}")
    print(f"  Макс. просадка:        {r.max_drawdown_pct:>12.2f} %")
    print(f"  Перестроек сетки:      {r.rebuilds:>12d}   Стопов: {r.stops}")
    print("-" * 62)
    print(f"  Просто купить и держать: {r.hold_profit:>+10.2f} USDT ({r.hold_pct:+.2f}%)")
    winner = "СЕТКА" if r.net_profit > r.hold_profit else "ДЕРЖАТЬ"
    print(f"  На этом отрезке лучше:  {winner}")
    print("=" * 62)
    print("  Помни: прошлое не гарантирует будущее. Бэктест отвечает лишь")
    print("  на вопрос «как стратегия вела себя в таких условиях».")
    print("=" * 62)


def save_chart(curve: list, r: Result, klines: list):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from datetime import datetime
    except ImportError:
        print("matplotlib не установлен — график пропущен (pip install matplotlib)")
        return
    ts = [datetime.fromtimestamp(t / 1000) for t, _ in curve]
    eq = [e for _, e in curve]
    start_price = klines[0][4]
    hold = [r.budget / start_price * k[4] for k in klines[:len(curve)]]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.plot(ts, eq, label="Сеточная стратегия", linewidth=1.6)
    ax.plot(ts, hold, label="Купить и держать", linewidth=1.2, alpha=0.75)
    ax.axhline(r.budget, color="gray", linestyle="--", linewidth=0.8, label="Стартовый бюджет")
    ax.set_title(f"{r.symbol}: сетка ±{r.range_pct}% × {r.levels} за {r.days} дн.")
    ax.set_ylabel("USDT")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig("equity_curve.png", dpi=130)
    print("\nГрафик сохранён: equity_curve.png")


def sweep(klines, budget, stop_extra, rebuild_up, symbol, days):
    ranges = [3.0, 5.0, 7.0, 10.0]
    level_opts = [8, 12, 16, 20]
    results = []
    total = len(ranges) * len(level_opts)
    n = 0
    for rng in ranges:
        for lv in level_opts:
            n += 1
            print(f"Перебор {n}/{total}: ±{rng}% × {lv}...", end="\r")
            res, _ = simulate(klines, budget, rng, lv, stop_extra,
                              rebuild_up, symbol, days)
            results.append(res)
    results.sort(key=lambda x: x.net_profit, reverse=True)

    print("\n")
    print(f"{'Сетка':>12} | {'Итог USDT':>10} | {'Итог %':>8} | {'Сделок':>6} | "
          f"{'MaxDD %':>7} | {'Стопов':>6}")
    print("-" * 62)
    for r in results:
        print(f"±{r.range_pct:>4.1f}% x{r.levels:<3d} | {r.net_profit:>+10.2f} | "
              f"{r.net_pct:>+7.2f}% | {r.trades:>6d} | {r.max_drawdown_pct:>7.2f} | {r.stops:>6d}")
    print("-" * 62)
    hold = results[0].hold_profit
    print(f"Купить и держать на том же отрезке: {hold:+.2f} USDT")
    print("\nВНИМАНИЕ про подгонку: лучшие параметры прошлого не обязаны быть")
    print("лучшими в будущем. Выбирай не строку-чемпиона, а параметры, которые")
    print("показывают приемлемый результат НА РАЗНЫХ отрезках (--days 30/90/180).")


# ----------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="GridLab — бэктест сеточной стратегии")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--interval", default="5", help="минут в свече: 1/5/15")
    ap.add_argument("--budget", type=float, default=500)
    ap.add_argument("--range", dest="range_pct", type=float, default=5.0)
    ap.add_argument("--levels", type=int, default=10)
    ap.add_argument("--stop", type=float, default=3.0, help="стоп ниже сетки, %%")
    ap.add_argument("--no-rebuild-up", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="перебор параметров")
    a = ap.parse_args()

    klines = download_klines(a.symbol, a.interval, a.days)
    if len(klines) < 100:
        sys.exit("Слишком мало данных")

    if a.sweep:
        sweep(klines, a.budget, a.stop, not a.no_rebuild_up, a.symbol, a.days)
    else:
        res, curve = simulate(klines, a.budget, a.range_pct, a.levels,
                              a.stop, not a.no_rebuild_up, a.symbol, a.days)
        print_report(res)
        save_chart(curve, res, klines)


if __name__ == "__main__":
    main()
