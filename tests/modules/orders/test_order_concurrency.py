"""Concurrencia realista sobre una única PendingOrder en SQLite."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.database import register_models
from app.modules.history.repository import LocalTransactionRepository
from app.modules.orders.models import PendingOrder
from app.modules.orders.repository import PendingOrderRepository
from app.modules.orders.service import OrderService
from app.modules.settings.models import UserSettings


class FixedBalanceService:
    async def get_balance(self, *args, **kwargs):
        return SimpleNamespace(
            checking_usd=100.0,
            investment_cash_usd=100.0,
            available_usd=100.0,
        )


@pytest.mark.asyncio
async def test_one_hundred_confirmations_execute_once(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "TRADING_ENABLED", False)
    register_models()
    engine = create_engine(
        f"sqlite:///{tmp_path / 'concurrency.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    order_repo = PendingOrderRepository()
    tx_repo = LocalTransactionRepository()

    try:
        with SessionLocal() as setup:
            user = UserSettings(
                telegram_user_id=123456789,
                default_currency="CLP",
                report_time="09:00",
                timezone="UTC",
                alerts_enabled=True,
            )
            setup.add(user)
            setup.flush()
            order = order_repo.create(
                setup,
                user.id,
                "VOO",
                50.0,
                datetime.now(timezone.utc) + timedelta(hours=1),
                "concurrent-order",
            )
            setup.commit()
            user_id, order_id = user.id, order.id

        async def confirm_once():
            with SessionLocal() as session:
                user_for_attempt = session.get(UserSettings, user_id)
                service = OrderService(
                    order_repo=order_repo,
                    tx_repo=tx_repo,
                    client=SimpleNamespace(),
                    balance_service=FixedBalanceService(),
                )
                return await service.confirm_order(session, order_id, user_for_attempt)

        results = await asyncio.gather(*(confirm_once() for _ in range(100)))

        assert sum(result.success for result in results) == 1
        assert sum(result.already_processed for result in results) == 99
        with Session(engine) as verify:
            assert verify.get(PendingOrder, order_id).external_order_id.startswith("SIM-")
            assert verify.query(PendingOrder).count() == 1
    finally:
        engine.dispose()
