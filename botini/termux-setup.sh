#!/data/data/com.termux/files/usr/bin/bash
# Установка Grid Suite в Termux. Запуск: bash termux-setup.sh
set -e
echo "== Grid Suite: установка в Termux =="
pkg update -y
pkg install -y python nano
pip install --upgrade pip wheel
pip install -r bot/requirements.txt
pip install requests   # лаборатория (график в Termux не ставим — не нужен боту)

# уведомления на шторку телефона (опционально, нужно приложение Termux:API)
pkg install -y termux-api || true

if [ ! -f bot/.env ]; then
    cp bot/.env.example bot/.env
    echo ""
    echo ">> Создан bot/.env — впиши ключи командой:  nano bot/.env"
    echo "   (сохранить: Ctrl+O затем Enter, выйти: Ctrl+X)"
fi
echo ""
echo "== Готово. Запуск бота:  bash termux-run.sh =="
