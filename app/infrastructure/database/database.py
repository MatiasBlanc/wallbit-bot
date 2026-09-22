"""Database setup and session management."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.infrastructure.database.base import Base

# Use SQLite with check_same_thread=False for multi-threaded/async environments
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not settings.DATABASE_URL.startswith("sqlite"),
)


@event.listens_for(Engine, "connect")
def _configure_sqlite_connection(dbapi_connection: sqlite3.Connection, connection_record: object) -> None:
    """Activa integridad referencial y espera acotada para conexiones SQLite.

    SQLite ignora claves foráneas si no se habilitan por conexión. WAL disminuye los
    bloqueos entre el polling y los jobs en una instancia única.
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

# Los handlers construyen respuestas tras el commit; no necesitan recargar cada atributo.
# Las transiciones de órdenes vuelven a validar su estado directamente en SQL.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def register_models() -> None:
    """Carga los modelos de todos los módulos en el registro ORM compartido.

    Returns:
        None. Puede invocarse varias veces sin duplicar tablas ni mappers.
    """
    # Las relaciones por nombre necesitan todos los modelos antes del primer uso.
    import app.infrastructure.notifications.models  # noqa: F401
    import app.modules.alerts.models  # noqa: F401
    import app.modules.auth.models  # noqa: F401
    import app.modules.dca.models  # noqa: F401
    import app.modules.history.models  # noqa: F401
    import app.modules.orders.models  # noqa: F401
    import app.modules.settings.models  # noqa: F401


def _migrate_sqlite_schema() -> None:
    """Aplica migraciones SQLite aditivas y registra su versión.

    SQLAlchemy no altera tablas ya creadas con ``create_all``. Cada paso debe ser
    compatible con instalaciones anteriores y seguro de ejecutar más de una vez.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        ))
        applied_versions = set(connection.execute(text("SELECT version FROM schema_migrations")).scalars())
        if 1 not in applied_versions:
            inspector = inspect(connection)
            dca_columns = {column["name"] for column in inspector.get_columns("dca_rules")}
            if "asset_name" not in dca_columns:
                connection.execute(text("ALTER TABLE dca_rules ADD COLUMN asset_name VARCHAR(200)"))
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES (1)"))
        if 2 not in applied_versions:
            # notification_outbox se crea mediante metadata antes de este paso.
            connection.execute(text("INSERT INTO schema_migrations (version) VALUES (2)"))


def init_db() -> None:
    """Registra modelos, crea tablas nuevas y aplica migraciones SQLite aditivas.

    Returns:
        None. Conserva columnas y datos existentes y agrega los índices declarados.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Si falla la creación o migración de tablas.
    """
    register_models()
    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_schema()
    # create_all omite los índices nuevos cuando la tabla ya existía.
    for table in Base.metadata.sorted_tables:
        for index in table.indexes:
            index.create(bind=engine, checkfirst=True)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for database sessions with automatic commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
