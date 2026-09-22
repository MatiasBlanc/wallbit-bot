"""Comandos administrativos locales de la instancia."""

import argparse
import asyncio
import importlib.util
import sys
from collections.abc import Sequence
from urllib.parse import urlsplit

from telegram import Bot
from telegram.error import TelegramError

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


async def _check_telegram() -> bool:
    """Comprueba el token de Telegram sin iniciar polling.

    Returns:
        True si Telegram reconoce el bot configurado; False ante token inválido o red no disponible.
    """
    if not settings.TELEGRAM_BOT_TOKEN or settings.TELEGRAM_ALLOWED_USER_ID <= 0:
        return False
    try:
        async with Bot(settings.TELEGRAM_BOT_TOKEN) as bot:
            await bot.get_me()
        return True
    except (TelegramError, OSError, ValueError):
        return False


def doctor() -> int:
    """Imprime un diagnóstico sin mostrar secretos ni respuestas financieras."""
    telegram_configured = bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ALLOWED_USER_ID > 0)
    telegram_ok = asyncio.run(_check_telegram()) if telegram_configured else False
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

    return 0 if telegram_ok and wallbit_ok and database_ok and scheduler_ok else 1


def run_backup(target_dir: str = "backups", keep: int = 7) -> int:
    try:
        from app.infrastructure.database.backup import create_sqlite_backup
        backup_file = create_sqlite_backup(target_dir=target_dir, keep=keep)
        print(f"Respaldo creado con éxito en: {backup_file}")
        return 0
    except Exception as err:
        print(f"ERROR: Falló el respaldo: {err}", file=sys.stderr)
        return 1


def verify_backup(backup_file: str) -> int:
    """Verifica un respaldo SQLite antes de copiarlo o probar una restauración.

    Args:
        backup_file: Ruta de la copia SQLite creada por el comando ``backup``.

    Returns:
        0 cuando SQLite confirma integridad; 1 ante un error verificable.
    """
    try:
        from app.infrastructure.database.backup import verify_sqlite_backup

        verify_sqlite_backup(backup_file)
        print(f"Respaldo íntegro: {backup_file}")
        return 0
    except Exception as error:
        print(f"ERROR: El respaldo no es válido: {error}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    parser.add_argument("command", choices=("doctor", "backup", "verify-backup"))
    parser.add_argument("--dir", default="backups", help="Directorio de destino para respaldos")
    parser.add_argument("--keep", type=int, default=7, help="Cantidad de copias a conservar")
    parser.add_argument("--file", help="Archivo SQLite que se debe verificar")
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return doctor()
    if args.command == "backup":
        return run_backup(target_dir=args.dir, keep=args.keep)
    if args.command == "verify-backup":
        if not args.file:
            parser.error("verify-backup requiere --file RUTA")
        return verify_backup(args.file)
    return 1


if __name__ == "__main__":
    sys.exit(main())
