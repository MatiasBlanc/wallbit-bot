"""Utilidad de respaldos atómicos y consistentes para bases de datos SQLite."""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_sqlite_path() -> Path | None:
    """Extrae la ruta al archivo SQLite a partir de DATABASE_URL."""
    db_url = settings.DATABASE_URL
    if not db_url.startswith("sqlite"):
        return None

    # Handle sqlite:////data/wallbit.db vs sqlite:///wallbit.db
    if db_url.startswith("sqlite:////"):
        path_str = "/" + db_url[len("sqlite:////"):]
    elif db_url.startswith("sqlite:///"):
        path_str = db_url[len("sqlite:///"):]
    else:
        parsed = urlsplit(db_url)
        path_str = parsed.path

    path = Path(path_str)
    return path


def create_sqlite_backup(target_dir: str | Path = "backups", keep: int = 7) -> Path:
    """Crea una copia de seguridad atómica usando la API de backup nativa de SQLite.

    Args:
        target_dir: Directorio de destino para el archivo .db respaldado.
        keep: Cantidad de copias históricas a conservar (rotación).

    Returns:
        Path al archivo de respaldo creado.

    Raises:
        FileNotFoundError: Si el archivo de base de datos original no existe.
        RuntimeError: Si la base de datos no es SQLite o falla el proceso.
    """
    source_path = get_sqlite_path()
    if source_path is None:
        raise RuntimeError(f"DATABASE_URL no es SQLite: {settings.DATABASE_URL}")

    if not source_path.exists():
        raise FileNotFoundError(f"El archivo de base de datos no existe en: {source_path}")

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    backup_file = target_dir / f"wallbit_backup_{timestamp}.db"

    logger.info(f"Iniciando respaldo atómico de {source_path} en {backup_file}...")

    source_conn = sqlite3.connect(str(source_path))
    dest_conn = sqlite3.connect(str(backup_file))

    try:
        with dest_conn:
            source_conn.backup(dest_conn, pages=100)
    finally:
        dest_conn.close()
        source_conn.close()

    size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)
    logger.info(f"Respaldo completado con éxito: {backup_file} ({size_mb} MB)")

    # Rotación de respaldos viejos
    _rotate_backups(target_dir, keep=keep)

    return backup_file


def verify_sqlite_backup(backup_file: str | Path) -> None:
    """Comprueba la integridad de un respaldo SQLite sin modificarlo.

    Args:
        backup_file: Ruta al archivo generado por :func:`create_sqlite_backup`.

    Returns:
        None si SQLite confirma que la base es íntegra.

    Raises:
        FileNotFoundError: Si el respaldo no existe.
        RuntimeError: Si SQLite detecta corrupción o no puede abrir el archivo.
    """
    path = Path(backup_file)
    if not path.is_file():
        raise FileNotFoundError(f"El respaldo no existe: {path}")
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as error:
        raise RuntimeError(f"No se pudo abrir el respaldo: {path}") from error
    if result is None or result[0] != "ok":
        detail = result[0] if result else "sin resultado"
        raise RuntimeError(f"El respaldo no pasó integrity_check: {detail}")


def _rotate_backups(target_dir: Path, keep: int) -> None:
    """Elimina copias antiguas si superan el límite configurado."""
    if keep <= 0:
        return
    backups = sorted(target_dir.glob("wallbit_backup_*.db"), key=os.path.getmtime, reverse=True)
    if len(backups) > keep:
        for old_backup in backups[keep:]:
            try:
                old_backup.unlink()
                logger.info(f"Copia rotada y eliminada: {old_backup.name}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar respaldo antiguo {old_backup}: {e}")
