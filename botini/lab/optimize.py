"""
Optimize — мост между лабораторией и ботом.

Делает то, что вручную делать лень, а надо:
  1. Скачивает историю за самый длинный период один раз.
  2. Прогоняет каждую комбинацию сетки на НЕСКОЛЬКИХ отрезках (30/90/180 дн).
  3. Оценивает по ХУДШЕМУ отрезку — это защита от подгонки под удачный период.
  4. По флагу --apply вписывает победителя прямо в config.yaml бота
     (с резервной копией config.yaml.bak).

Примеры:
  python optimize.py --symbol BTCUSDT
  python optimize.py --symbol BTCUSDT --apply ../bot/config.yaml
  python optimize.py --symbol ETHUSDT --periods 30,60,120 --budget 1000
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

import backtest as bt

RANGES = [3.0, 5.0, 7.0, 10.0]
LEVELS = [8, 12, 16, 20]


def slice_days(klines: list, days: int, interval_min: int) -> list:
    per_day = 1440 // interval_min
    need = days * per_day
    return klines[-need:] if len(klines) > need else klines


def run_optimization(klines_full: list, periods: list[int], interval_min: int,
                     budget: float, stop_extra: float, symbol: str):
    combos = []
    total = len(RANGES) * len(LEVELS)
    n = 0
    for rng in RANGES:
        for lv in LEVELS:
            n += 1
            print(f"Комбинация {n}/{total}: ±{rng}% × {lv} на {len(periods)} отрезках...",
                  end="\r")
            per_period = []
            dd_worst = 0.0
            for days in periods:
                ks = slice_days(klines_full, days, interval_min)
                res, _ = bt.simulate(ks, budget, rng, lv, stop_extra,
                                     rebuild_up=True, symbol=symbol, days=days)
                per_period.append(res.net_pct)
                dd_worst = max(dd_worst, res.max_drawdown_pct)
            combos.append({
                "range": rng, "levels": lv,
                "per_period": per_period,
                "worst": min(per_period),
                "avg": sum(per_period) / len(per_period),
                "max_dd": dd_worst,
            })
    print(" " * 70, end="\r")

    # Главный критерий — результат худшего отрезка. Тай-брейк — средний.
    combos.sort(key=lambda c: (c["worst"], c["avg"]), reverse=True)
    return combos


def print_table(combos, periods):
    hdr_periods = " | ".join(f"{d:>4d}д %" for d in periods)
    print()
    print(f"{'Сетка':>12} | {hdr_periods} | {'Худший':>7} | {'MaxDD':>6}")
    print("-" * (16 + 10 * len(periods) + 20))
    for c in combos:
        pp = " | ".join(f"{x:>+6.2f}" for x in c["per_period"])
        print(f"±{c['range']:>4.1f}% x{c['levels']:<3d} | {pp} | "
              f"{c['worst']:>+7.2f} | {c['max_dd']:>5.1f}%")
    print("-" * (16 + 10 * len(periods) + 20))


def apply_to_config(config_path: Path, rng: float, levels: int, symbol: str):
    if not config_path.exists():
        sys.exit(f"Конфиг не найден: {config_path}")
    text = config_path.read_text(encoding="utf-8")

    backup = config_path.with_suffix(".yaml.bak")
    shutil.copy(config_path, backup)

    def set_param(t: str, key: str, value) -> str:
        pattern = rf"(?m)^({key}\s*:\s*)\S+"
        if not re.search(pattern, t):
            sys.exit(f"В конфиге нет параметра {key}")
        return re.sub(pattern, rf"\g<1>{value}", t)

    text = set_param(text, "grid_range_pct", rng)
    text = set_param(text, "grid_levels", levels)

    m = re.search(r"(?m)^symbol\s*:\s*(\S+)", text)
    cfg_symbol = m.group(1) if m else "?"
    if cfg_symbol != symbol:
        print(f"⚠ В конфиге бота symbol={cfg_symbol}, а оптимизация была для {symbol}.")
        ans = input(f"  Обновить symbol на {symbol}? [y/N]: ").strip().lower()
        if ans == "y":
            text = set_param(text, "symbol", symbol)

    config_path.write_text(text, encoding="utf-8")
    print(f"\n✅ Записано в {config_path}: grid_range_pct={rng}, grid_levels={levels}")
    print(f"   Резервная копия: {backup}")
    print("   Дальше: cd в папку бота -> python bot.py (testnet: true!)")


def main():
    ap = argparse.ArgumentParser(description="Мультипериодная оптимизация сетки")
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--periods", default="30,90,180",
                    help="отрезки в днях через запятую")
    ap.add_argument("--interval", default="5", help="минут в свече")
    ap.add_argument("--budget", type=float, default=500)
    ap.add_argument("--stop", type=float, default=3.0)
    ap.add_argument("--apply", metavar="CONFIG",
                    help="путь к config.yaml бота — вписать победителя")
    a = ap.parse_args()

    periods = sorted(int(x) for x in a.periods.split(","))
    interval_min = int(a.interval)

    klines = bt.download_klines(a.symbol, a.interval, max(periods))
    if len(klines) < 100:
        sys.exit("Слишком мало данных")

    combos = run_optimization(klines, periods, interval_min,
                              a.budget, a.stop, a.symbol)
    print_table(combos, periods)

    best = combos[0]
    print(f"\nЛучшая по устойчивости: ±{best['range']}% × {best['levels']} "
          f"(худший отрезок: {best['worst']:+.2f}%, просадка до {best['max_dd']:.1f}%)")

    if best["worst"] < 0:
        print("\n⚠ ВНИМАНИЕ: даже лучшая комбинация была в минусе на одном из")
        print("  отрезков. Это сигнал, что рынок этой монеты сейчас плохо")
        print("  подходит для грида. Подумай дважды, прежде чем запускать.")

    if a.apply:
        if best["worst"] < 0:
            ans = input("Всё равно записать в конфиг? [y/N]: ").strip().lower()
            if ans != "y":
                print("Отменено — разумно.")
                return
        apply_to_config(Path(a.apply), best["range"], best["levels"], a.symbol)


if __name__ == "__main__":
    main()
