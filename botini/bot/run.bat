@echo off
chcp 65001 > nul
title Bybit Grid Bot v2
:loop
python bot.py
echo.
echo Бот завершился. Перезапуск через 30 секунд... (закрой окно, чтобы остановить)
timeout /t 30 /nobreak > nul
goto loop
