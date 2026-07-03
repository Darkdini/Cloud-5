"""Уведомления без Telegram — всё видно прямо в консоли Termux.

Каждое событие пишется в лог (значит попадает и в bot.log, и в терминал,
за которым ты наблюдаешь), а если установлен Termux:API — важное ещё и
дублируется в шторку телефона. Никаких токенов и внешних сервисов.
"""

import logging
import shutil
import subprocess

log = logging.getLogger("gridbot")


class Notifier:
    def __init__(self):
        # Termux: если есть команда termux-notification — шлём и в шторку телефона
        self.termux = shutil.which("termux-notification") is not None
        if self.termux:
            log.info("Termux:API найден — важные события пойдут и в шторку телефона")
        else:
            log.info("Уведомления идут в консоль и bot.log (Telegram отключён)")

    def send(self, text: str):
        # в консоль/лог одной строкой (многострочное схлопываем в « | »)
        log.info("🔔 %s", text.replace("\n", " | "))

        if self.termux:
            try:
                subprocess.run(
                    ["termux-notification", "-t", "Grid Bot",
                     "-c", text, "--id", "gridbot"],
                    timeout=8, check=False,
                )
            except Exception as e:
                log.debug("termux-notification: %s", e)
