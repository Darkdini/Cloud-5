#!/bin/bash
# Watchdog: перезапускает бота при падении
while true; do
    python3 bot.py
    echo "Бот завершился. Перезапуск через 30 сек... (Ctrl+C дважды — остановить)"
    sleep 30
done
