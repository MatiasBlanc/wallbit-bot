"""Tests for security, authorization, and secret sanitization."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.core.logging import SecretSanitizingFilter
from app.core.security import is_user_authorized, restricted


def test_is_user_authorized(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", 123456789)
    assert is_user_authorized(123456789) is True
    assert is_user_authorized(987654321) is False
    assert is_user_authorized(0) is False


@pytest.mark.asyncio
async def test_restricted_decorator_blocks_unauthorized_user(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", 123456789)

    called = False

    @restricted
    async def sample_handler(update, context):
        nonlocal called
        called = True

    # Unauthorized update
    update = MagicMock()
    update.effective_user.id = 999999999
    update.effective_message.reply_text = AsyncMock()
    update.callback_query = None

    context = MagicMock()
    await sample_handler(update, context)

    assert called is False
    update.effective_message.reply_text.assert_called_once_with("Este bot es privado.")


@pytest.mark.asyncio
async def test_restricted_decorator_allows_authorized_user(monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", 123456789)

    called = False

    @restricted
    async def sample_handler(update, context):
        nonlocal called
        called = True

    update = MagicMock()
    update.effective_user.id = 123456789
    context = MagicMock()

    await sample_handler(update, context)
    assert called is True


def test_secret_sanitizing_filter():
    secret_key = "wb_live_secret_key_999888777"
    bot_token = "123456789:AAH_super_secret_bot_token_xyz"
    filter_obj = SecretSanitizingFilter(secrets=[secret_key, bot_token])

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg=f"Calling Wallbit with key {secret_key} and token {bot_token}",
        args=(),
        exc_info=None,
    )
    filter_obj.filter(record)

    assert secret_key not in record.msg
    assert bot_token not in record.msg
    assert "***REDACTED***" in record.msg
