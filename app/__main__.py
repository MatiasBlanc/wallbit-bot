"""Comandos administrativos locales de la instancia."""

import argparse
import asyncio
import importlib.util
import sys
from collections.abc import Sequence
from urllib.parse import urlsplit

from app.core.config import settings
from app.infrastructure.database.database import engine, init_db
from app.infrastructure.wallbit.client import WallbitClient


def _ok(value: bool) -> str:
    return "OK" if value else "ERROR"


def _check_database() -> bool:
    try:
        init_db()
        with engine.connect():
            return True
    except Exception:
        return False


async def _check_wallbit() -> bool:
    if not settings.WALLBIT_API_KEY:
        return False
    client = WallbitClient()
    try:
        return await client.check_connection()
    finally:
        await client.close()


def doctor() -> int:
    """Imprime un diagnóstico sin mostrar secretos ni respuestas financieras."""
    telegram_ok = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ALLOWED_USER_ID > 0)
    wallbit_url = urlsplit(settings.WALLBIT_BASE_URL)
    wallbit_configured = bool(settings.WALLBIT_API_KEY and wallbit_url.scheme == "https" and wallbit_url.hostname)
    database_ok = _check_database()
    scheduler_ok = importlib.util.find_spec("apscheduler") is not None
    wallbit_ok = asyncio.run(_check_wallbit()) if wallbit_configured else False

    print(f"Telegram        {_ok(telegram_ok)}")
    print(f"Wallbit         {_ok(wallbit_ok)}")
    print(f"Database        {_ok(database_ok)}")
    print(f"Scheduler       {_ok(scheduler_ok)}")
    print(f"AI              {'DISABLED' if not settings.AI_ENABLED else 'ENABLED'}")
    print(f"Trading         {'ENABLED' if settings.TRADING_ENABLED else 'DISABLED'}")

    return 0 if telegram_ok and wallbit_configured and database_ok and scheduler_ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    parser.add_argument("command", choices=("doctor",))
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor()
    return 1


if __name__ == "__main__":
    sys.exit(main())
