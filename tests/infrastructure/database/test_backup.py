"""Pruebas de respaldo atómico y rotación de base de datos SQLite."""

import sqlite3
from pathlib import Path

import pytest

from app.core.config import settings
from app.infrastructure.database.backup import create_sqlite_backup, get_sqlite_path, verify_sqlite_backup


def test_get_sqlite_path(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///wallbit.db")
    assert get_sqlite_path() == Path("wallbit.db")

    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:////data/wallbit.db")
    assert get_sqlite_path() == Path("/data/wallbit.db")


def test_create_sqlite_backup_and_rotation(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
    conn.execute("INSERT INTO users (name) VALUES ('Alice');")
    conn.commit()
    conn.close()

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_file}")

    backup_dir = tmp_path / "backups"

    # Create 3 backups with keep=2
    b1 = create_sqlite_backup(target_dir=backup_dir, keep=2)
    assert b1.exists()

    b2 = create_sqlite_backup(target_dir=backup_dir, keep=2)
    assert b2.exists()

    b3 = create_sqlite_backup(target_dir=backup_dir, keep=2)
    assert b3.exists()

    # Verify rotation kept only 2 backups
    backups = list(backup_dir.glob("wallbit_backup_*.db"))
    assert len(backups) == 2

    # Verify backup integrity by querying restored database
    b_conn = sqlite3.connect(str(b3))
    cursor = b_conn.cursor()
    cursor.execute("SELECT name FROM users WHERE id = 1;")
    row = cursor.fetchone()
    assert row[0] == "Alice"
    b_conn.close()
    verify_sqlite_backup(b3)


def test_verify_sqlite_backup_rejects_invalid_file(tmp_path):
    corrupted_file = tmp_path / "corrupted.db"
    corrupted_file.write_text("esto no es SQLite")

    with pytest.raises(RuntimeError, match="No se pudo abrir"):
        verify_sqlite_backup(corrupted_file)


def test_backup_fails_if_db_missing(tmp_path, monkeypatch):
    missing_file = tmp_path / "missing.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{missing_file}")

    with pytest.raises(FileNotFoundError):
        create_sqlite_backup(target_dir=tmp_path / "backups")
