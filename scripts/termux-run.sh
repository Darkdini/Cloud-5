#!/data/data/com.termux/files/usr/bin/bash
# Запуск бота 24/7 на телефоне через Termux.
# - держит CPU включённым (wake-lock), чтобы Android не усыплял процесс
# - перезапускает бота, если он упал
# Использование:  bash ~/Cloud-5/scripts/termux-run.sh

set -u
cd "$(dirname "$0")/.." || exit 1

# не давать телефону усыплять процесс
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock

cleanup() {
    command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
    echo "Остановлено."
    exit 0
}
trap cleanup INT TERM

echo "Бот запускается. Остановить: Ctrl+C"
while true; do
    python -m cloud5.bot.main
    code=$?
    # Ctrl+C / штатная остановка — выходим
    if [ "$code" -eq 0 ] || [ "$code" -eq 130 ]; then
        cleanup
    fi
    echo "⚠️  Бот упал (код $code). Перезапуск через 5 секунд..."
    sleep 5
done
