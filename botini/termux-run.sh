#!/data/data/com.termux/files/usr/bin/bash
# Запуск бота в Termux с блокировкой сна и авторестартом
cd "$(dirname "$0")/bot"
termux-wake-lock 2>/dev/null
trap "termux-wake-unlock 2>/dev/null" EXIT
echo "Wake-lock включён: Android не усыпит бота."
echo "Панель в браузере телефона: http://localhost:8899"
while true; do
    python bot.py
    code=$?
    if [ $code -eq 0 ]; then break; fi
    echo "Бот упал (код $code). Перезапуск через 30 сек... (Ctrl+C — выйти)"
    sleep 30
done
