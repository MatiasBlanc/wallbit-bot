"""Pytest fixtures and test configuration."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.base import Base
from app.infrastructure.database.database import register_models
from app.infrastructure.wallbit.client import WallbitClient
from app.infrastructure.wallbit.schemas.balance import CheckingBalanceItem, StockBalanceItem
from app.infrastructure.wallbit.schemas.orders import ExchangeRateData, TradeResult
from app.infrastructure.wallbit.schemas.portfolio import AssetDetails
from app.infrastructure.wallbit.schemas.transactions import TransactionCurrency, TransactionItem, TransactionsData
from app.modules.alerts.repository import AlertRepository
from app.modules.alerts.service import AlertService
from app.modules.balance.service import BalanceService
from app.modules.dca.repository import DCARuleRepository
from app.modules.dca.service import DCAService
from app.modules.history.repository import LocalTransactionRepository
from app.modules.history.service import HistoryService
from app.modules.orders.repository import PendingOrderRepository
from app.modules.orders.service import OrderService
from app.modules.portfolio.service import PortfolioService
from app.modules.reports.service import ReportService
from app.modules.settings.models import UserSettings
from app.modules.settings.repository import UserSettingsRepository
from app.shared.exchange.providers import WallbitExchangeRateProvider
from app.shared.exchange.service import ExchangeRateService


@pytest.fixture
def db_session():
    """In-memory SQLite database session for isolated testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    register_models()
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_wallbit_client():
    """Mock WallbitClient that never calls real external APIs."""
    client = AsyncMock(spec=WallbitClient)
    client.api_key = "test_key_123"
    client.base_url = "https://api.wallbit.io"

    # Default mock responses
    client.check_connection.return_value = True

    client.get_checking_balance.return_value = [
        CheckingBalanceItem(currency="USD", balance=220.50),
    ]

    client.get_stocks_balance.return_value = [
        StockBalanceItem(symbol="USD", shares=85.20),
        StockBalanceItem(symbol="VOO", shares=1.0),
        StockBalanceItem(symbol="AAPL", shares=2.0),
    ]

    def mock_get_asset(symbol: str):
        s = symbol.upper()
        if s == "VOO":
            return AssetDetails(symbol="VOO", name="Vanguard S&P 500 ETF", price=495.20)
        elif s == "AAPL":
            return AssetDetails(symbol="AAPL", name="Apple Inc.", price=180.00)
        elif s == "SPY":
            return AssetDetails(symbol="SPY", name="SPDR S&P 500 ETF Trust", price=510.00)
        from app.infrastructure.wallbit.exceptions import InvalidTickerError
        raise InvalidTickerError(s)

    client.get_asset.side_effect = mock_get_asset

    def mock_get_rate(source: str, dest: str):
        s, d = source.upper(), dest.upper()
        if s == d:
            rate = 1.0
        elif s == "USD" and d == "CLP":
            rate = 950.0
        elif s == "USD" and d == "ARS":
            rate = 1200.0
        elif s == "USD" and d == "EUR":
            rate = 0.92
        else:
            rate = 1.0
        return ExchangeRateData(
            source_currency=s,
            dest_currency=d,
            pair=f"{s}{d}",
            rate=rate,
        )

    client.get_exchange_rate.side_effect = mock_get_rate

    client.create_trade.return_value = TradeResult(
        id="ORD-12345678",
        symbol="VOO",
        direction="BUY",
        amount=50.0,
        shares=0.100969,
        status="REQUESTED",
    )

    client.get_transactions.return_value = TransactionsData(
        data=[
            TransactionItem(
                uuid="tx-1",
                type_id=1,
                source_currency=TransactionCurrency(code="USD"),
                dest_currency=TransactionCurrency(code="USD"),
                source_amount=50.0,
                dest_amount=50.0,
                status="COMPLETED",
                created_at="2026-09-03T10:30:00.000000Z",
                comment="buy VOO",
            )
        ],
        pages=1,
        current_page=1,
        count=1,
    )

    return client


@pytest.fixture
def user_repo():
    return UserSettingsRepository()


@pytest.fixture
def dca_repo():
    return DCARuleRepository()


@pytest.fixture
def order_repo():
    return PendingOrderRepository()


@pytest.fixture
def alert_repo():
    return AlertRepository()


@pytest.fixture
def tx_repo():
    return LocalTransactionRepository()


@pytest.fixture
def test_user(db_session: Session, user_repo: UserSettingsRepository) -> UserSettings:
    """Pre-created test user."""
    user = user_repo.get_or_create(db_session, telegram_user_id=123456789)
    user.default_currency = "CLP"
    user.timezone = "America/Santiago"
    user.report_time = "09:00"
    user.alerts_enabled = True
    db_session.commit()
    return user


@pytest.fixture
def exchange_service(mock_wallbit_client):
    provider = WallbitExchangeRateProvider(mock_wallbit_client)
    return ExchangeRateService(primary_provider=provider, cache_ttl_seconds=0)


@pytest.fixture
def balance_service(mock_wallbit_client, exchange_service):
    return BalanceService(client=mock_wallbit_client, exchange_service=exchange_service)


@pytest.fixture
def portfolio_service(mock_wallbit_client):
    return PortfolioService(client=mock_wallbit_client)


@pytest.fixture
def dca_service(dca_repo, order_service, mock_wallbit_client, balance_service):
    return DCAService(
        dca_repo=dca_repo,
        order_service=order_service,
        client=mock_wallbit_client,
        balance_service=balance_service,
    )


@pytest.fixture
def order_service(order_repo, tx_repo, mock_wallbit_client, balance_service):
    return OrderService(
        order_repo=order_repo,
        tx_repo=tx_repo,
        client=mock_wallbit_client,
        balance_service=balance_service,
    )


@pytest.fixture
def alert_service(alert_repo, mock_wallbit_client, exchange_service):
    return AlertService(
        alert_repo=alert_repo,
        client=mock_wallbit_client,
        exchange_service=exchange_service,
    )


@pytest.fixture
def history_service(mock_wallbit_client, tx_repo):
    return HistoryService(client=mock_wallbit_client, tx_repo=tx_repo)


@pytest.fixture
def report_service(balance_service, portfolio_service, exchange_service):
    return ReportService(
        balance_service=balance_service,
        portfolio_service=portfolio_service,
        exchange_service=exchange_service,
    )
