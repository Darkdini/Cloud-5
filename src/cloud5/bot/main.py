"""Запуск платформы: ``python -m cloud5.bot.main``."""

from __future__ import annotations

import asyncio

from cloud5.core.logging import get_logger, setup_logging
from cloud5.core.runtime import run_polling

log = get_logger("main")


def main() -> None:
    setup_logging()
    try:
        asyncio.run(run_polling())
    except (KeyboardInterrupt, SystemExit):
        log.info("shutdown")


if __name__ == "__main__":
    main()
