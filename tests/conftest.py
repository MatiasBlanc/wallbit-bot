"""Pytest fixtures and test configuration."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.db.models import UserSettings
from app.db.repositories.alert_repo import AlertRepository
from app.db.repositories.dca_repo import DCARuleRepository
from app.db.repositories.pending_order_repo import PendingOrderRepository
from app.db.repositories.transaction_repo import LocalTransactionRepository
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.alert_service import AlertService
from app.services.balance_service import BalanceService
from app.services.dca_service import DCAService
from app.services.exchange_service import (
    ExchangeRateService,
    WallbitExchangeRateProvider,
)
from app.services.history_service import HistoryService
from app.services.order_service import OrderService
from app.services.portfolio_service import PortfolioService
from app.services.report_service import ReportService
from app.wallbit.client import WallbitClient
from app.wallbit.schemas import (
    AssetDetails,
    CheckingBalanceItem,
    ExchangeRateData,
    StockBalanceItem,
    TradeResult,
    TransactionCurrency,
    TransactionItem,
    TransactionsData,
)


@pytest.fixture
def db_session():
    """In-memory SQLite database session for isolated testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
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
        from app.wallbit.exceptions import InvalidTickerError
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
def dca_service(dca_repo, order_repo, mock_wallbit_client, balance_service):
    return DCAService(
        dca_repo=dca_repo,
        order_repo=order_repo,
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
