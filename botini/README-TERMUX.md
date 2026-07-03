# Grid Suite в Termux — бот живёт в телефоне

## Шаг 1. Правильный Termux

Ставь **только из F-Droid** (f-droid.org): приложения **Termux** и,
по желанию, **Termux:API** (уведомления в шторку) и **Termux:Boot**
(автозапуск при включении телефона).
Версия Termux из Google Play сломана — не используй её.

## Шаг 2. Установка

Скинь grid-suite.zip в папку Download телефона, затем в Termux:
```bash
pkg install -y unzip
termux-setup-storage        # разреши доступ к файлам
cd ~
unzip /sdcard/Download/grid-suite.zip
cd grid-suite
bash termux-setup.sh        # ставит всё сам
```

## Шаг 3. Ключи

```bash
nano bot/.env
```
Впиши BYBIT_API_KEY и BYBIT_API_SECRET (создаются через браузер на
testnet.bybit.com — в мобильном приложении Bybit этой функции нет,
включи в браузере «версию для ПК»).
Сохранить: Ctrl+O, Enter. Выйти: Ctrl+X.
В .env только ключ и секрет Bybit — Telegram больше не нужен. Всё видно
прямо в терминале Termux (подключение, свеча, каждая сделка), а если
установлен Termux:API — важное дублируется и в шторку телефона.

## Шаг 4. Не дай Android убить бота

Настройки телефона → Приложения → Termux → Батарея →
**«Без ограничений» / отключить оптимизацию**.
Это обязательный шаг: иначе система прибьёт бота через 20-30 минут
за «фоновую активность». На Xiaomi/Huawei/Samsung свои названия
(«Автозапуск», «Защищённые приложения») — включи всё, что позволяет
жить в фоне.

## Шаг 5. Запуск

```bash
bash termux-run.sh
```
Скрипт сам включает wake-lock (телефон не уснёт) и перезапускает бота
при падении. Панель — в браузере телефона: **http://localhost:8899**

Свернуть Termux можно — бот продолжит работать (в шторке будет висеть
значок wake-lock). Смахнуть Termux из недавних = убить бота.

## Автозапуск при включении телефона (опционально)

Нужно приложение Termux:Boot из F-Droid. Один раз открой его, затем:
```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/gridbot.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/grid-suite && bash termux-run.sh
EOF
chmod +x ~/.termux/boot/gridbot.sh
```
Теперь после перезагрузки телефона бот стартует сам и восстанавливает
ордера из state.json.

## Оптимизация параметров в Termux

Работает без графиков (matplotlib не нужен):
```bash
cd ~/grid-suite/lab
python optimize.py --symbol BTCUSDT --apply ../bot/config.yaml
```

## Честные ограничения телефона

- Нет сети / телефон разрядился → бот слеп: ордера на бирже живут,
  но стоп-лосс и реакции не работают, пока бот лежит
- Агрессивные прошивки (MIUI, EMUI) иногда убивают фон несмотря на
  настройки — первые сутки поглядывай, жив ли процесс
- Для testnet-обкатки телефон отличен; для реальных денег надёжнее
  ПК, который не выключается

## Мини-шпаргалка команд

| Что | Команда |
|---|---|
| Запуск | `cd ~/grid-suite && bash termux-run.sh` |
| Стоп | Ctrl+C (или кнопка на панели localhost:8899) |
| Ключи | `nano ~/grid-suite/bot/.env` |
| Настройки | `nano ~/grid-suite/bot/config.yaml` |
| Лог | `tail -f ~/grid-suite/bot/bot.log` |
| Оптимизация | `cd ~/grid-suite/lab && python optimize.py --apply ../bot/config.yaml` |
