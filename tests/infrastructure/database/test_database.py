"""Regresiones del registro de modelos y compatibilidad del esquema SQLite."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.infrastructure.database import database
from app.modules.settings.models import UserSettings


def test_init_db_registers_all_models_in_fresh_process(tmp_path):
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{tmp_path / 'fresh.db'}"
    result = subprocess.run(
        [sys.executable, "-c", """
from app.infrastructure.database.database import init_db, engine
from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers
init_db()
init_db()
configure_mappers()
assert set(inspect(engine).get_table_names()) == {
    'user_settings', 'dca_rules', 'pending_orders', 'alerts', 'local_transactions', 'wallbit_credentials',
    'notification_outbox', 'schema_migrations'
}
engine.dispose()
"""],
        env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_init_db_preserves_existing_schema_and_data(tmp_path, monkeypatch):
    db_path = tmp_path / "existing.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(Path(__file__).with_name("legacy_schema.sql").read_text())
        connection.execute("""
            INSERT INTO user_settings VALUES (
                1, 123456789, 'EUR', '10:30', 'UTC', 1,
                '2026-01-01 00:00:00', '2026-01-01 00:00:00', '2026-01-01'
            )
        """)
        connection.execute("""
            INSERT INTO dca_rules VALUES (
                1, 1, 'VOO', 50, 'weekly', 0, NULL, 1,
                '2026-01-01 00:00:00', '2026-01-01 00:00:00', NULL, '2026-01-05 00:00:00'
            )
        """)
        connection.execute("""
            INSERT INTO pending_orders VALUES (
                1, 1, 1, 'VOO', 50, 'pending', '2026-01-01 00:00:00',
                '2026-01-02 00:00:00', NULL, NULL, 'legacy-order'
            )
        """)
        before = connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()

    engine = create_engine(f"sqlite:///{db_path}")
    monkeypatch.setattr(database, "engine", engine)
    try:
        database.init_db()
        with Session(engine) as session:
            user = session.get(UserSettings, 1)
            assert user.default_currency == "EUR"
            assert user.last_daily_report == "2026-01-01"
            assert user.dca_rules[0].ticker == "VOO"
            order = user.pending_orders[0]
            assert order.idempotency_key == "legacy-order"
            assert order.dca_rule is user.dca_rules[0]
            assert user.alerts == []
            assert user.transactions == []

        with sqlite3.connect(db_path) as connection:
            after = connection.execute("SELECT name, sql FROM sqlite_master ORDER BY name").fetchall()
        before_entries = dict(before)
        after_entries = dict(after)
        assert all(
            after_entries[name] == sql
            for name, sql in before_entries.items()
            if name != "dca_rules"
        )
        assert "asset_name" in after_entries["dca_rules"]
        assert after_entries.keys() - before_entries.keys() == {
            "ix_pending_orders_status_expires", "ix_dca_rules_enabled_execution", "ix_alerts_active_user",
            "ix_local_transactions_user_date", "ix_local_transactions_user_ticker_type",
            "ix_dca_rules_user_enabled_execution",
            "wallbit_credentials", "sqlite_autoindex_wallbit_credentials_1", "ix_wallbit_credentials_is_active",
            "notification_outbox", "ix_notification_outbox_event_key",
            "ix_notification_outbox_user_id", "ix_notification_outbox_delivery", "schema_migrations",
        }

        # El esquema nuevo debe conservar también columnas, índices y restricciones.
        fresh_engine = create_engine("sqlite:///:memory:")
        try:
            monkeypatch.setattr(database, "engine", fresh_engine)
            database.init_db()
            old_schema, new_schema = inspect(engine), inspect(fresh_engine)
            assert old_schema.get_table_names() == new_schema.get_table_names()
            for table in old_schema.get_table_names():
                old_columns = old_schema.get_columns(table)
                new_columns = new_schema.get_columns(table)
                for columns in (old_columns, new_columns):
                    for column in columns:
                        column["type"] = str(column["type"])
                assert sorted(old_columns, key=lambda column: column["name"]) == sorted(
                    new_columns, key=lambda column: column["name"]
                )
                assert old_schema.get_foreign_keys(table) == new_schema.get_foreign_keys(table)
                assert old_schema.get_indexes(table) == new_schema.get_indexes(table)
                assert old_schema.get_pk_constraint(table) == new_schema.get_pk_constraint(table)
        finally:
            fresh_engine.dispose()
    finally:
        engine.dispose()
