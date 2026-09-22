"""Flujo Telegram para revisar órdenes cuyo resultado quedó indeterminado."""

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.orm import sessionmaker
from telegram.constants import ChatType

from app.bot.commands import get_orders_handler
from app.core.config import settings
from app.core.constants import ORDER_STATUS_EXECUTED, ORDER_STATUS_UNKNOWN
from app.infrastructure.database import database
from app.modules.orders.callbacks import get_order_reconciliation_callback


def _use_test_database(monkeypatch, db_session) -> None:
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(bind=db_session.get_bind(), expire_on_commit=False),
    )


def _make_update(user_id: int) -> MagicMock:
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.type = ChatType.PRIVATE
    update.effective_message.reply_text = AsyncMock()
    update.callback_query = None
    return update


async def test_orders_command_uses_local_owner_and_offers_resolution(
    order_service, user_repo, db_session, test_user, monkeypatch,
):
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", test_user.telegram_user_id)
    _use_test_database(monkeypatch, db_session)
    order = order_service.create_pending_order(db_session, test_user, "AAPL", 100.0)
    order_service.order_repo.update_status(db_session, order, ORDER_STATUS_UNKNOWN)
    db_session.commit()

    update = _make_update(test_user.telegram_user_id)
    await get_orders_handler(order_service, user_repo)(update, MagicMock())

    update.effective_message.reply_text.assert_awaited_once()
    call = update.effective_message.reply_text.call_args
    assert f"ID #{order.id}" in call.args[0]
    callback_data = [
        button.callback_data
        for row in call.kwargs["reply_markup"].inline_keyboard
        for button in row
    ]
    assert callback_data == [
        f"order_reconcile:executed:{order.id}",
        f"order_reconcile:failed:{order.id}",
    ]


async def test_reconciliation_callback_marks_execution_without_sending_trade(
    order_service, user_repo, db_session, test_user, mock_wallbit_client, monkeypatch,
):
    monkeypatch.setattr(settings, "TELEGRAM_ALLOWED_USER_ID", test_user.telegram_user_id)
    _use_test_database(monkeypatch, db_session)
    order = order_service.create_pending_order(db_session, test_user, "AAPL", 100.0)
    order_service.order_repo.update_status(db_session, order, ORDER_STATUS_UNKNOWN)
    db_session.commit()
    order_id = order.id

    update = _make_update(test_user.telegram_user_id)
    update.callback_query = MagicMock(data=f"order_reconcile:executed:{order_id}")
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()

    callback = get_order_reconciliation_callback(order_service, user_repo)
    await callback(update, MagicMock())

    db_session.expire_all()
    reconciled = order_service.order_repo.get_by_id(db_session, order_id)
    assert reconciled.status == ORDER_STATUS_EXECUTED
    assert reconciled.executed_at is not None
    assert order_service.tx_repo.count_by_user(db_session, test_user.id) == 1
    mock_wallbit_client.create_trade.assert_not_awaited()
    update.callback_query.edit_message_text.assert_awaited_once()
