"""Main application entry point for Wallbit Assistant Bot."""

import sys

from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

from app.bot.bot import create_bot_application
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db
from app.db.repositories.alert_repo import AlertRepository
from app.db.repositories.dca_repo import DCARuleRepository
from app.db.repositories.pending_order_repo import PendingOrderRepository
from app.db.repositories.transaction_repo import LocalTransactionRepository
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.jobs.scheduler import BotScheduler
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

setup_logging()
logger = get_logger("main")


def main() -> None:
    logger.info("Initializing Wallbit Assistant Bot...")

    # Validate essential environment variables
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in environment or .env file.")
        print("ERROR: TELEGRAM_BOT_TOKEN is missing. Please check your .env file.")
        sys.exit(1)

    if not settings.TELEGRAM_ALLOWED_USER_ID:
        logger.warning(
            "TELEGRAM_ALLOWED_USER_ID is not configured. The bot will reject all interactions for security."
        )

    # Initialize Database
    logger.info("Setting up database tables...")
    init_db()

    # Instantiate HTTP Client
    client = WallbitClient(
        base_url=settings.WALLBIT_BASE_URL,
        api_key=settings.WALLBIT_API_KEY,
    )

    # Instantiate Repositories
    user_repo = UserSettingsRepository()
    dca_repo = DCARuleRepository()
    order_repo = PendingOrderRepository()
    alert_repo = AlertRepository()
    tx_repo = LocalTransactionRepository()

    # Instantiate Services
    wallbit_rate_provider = WallbitExchangeRateProvider(client)
    exchange_service = ExchangeRateService(primary_provider=wallbit_rate_provider)
    balance_service = BalanceService(client=client, exchange_service=exchange_service)
    portfolio_service = PortfolioService(client=client)
    dca_service = DCAService(
        dca_repo=dca_repo,
        order_repo=order_repo,
        client=client,
        balance_service=balance_service,
    )
    order_service = OrderService(
        order_repo=order_repo,
        tx_repo=tx_repo,
        client=client,
        balance_service=balance_service,
    )
    alert_service = AlertService(
        alert_repo=alert_repo,
        client=client,
        exchange_service=exchange_service,
    )
    history_service = HistoryService(client=client, tx_repo=tx_repo)
    report_service = ReportService(
        balance_service=balance_service,
        portfolio_service=portfolio_service,
        exchange_service=exchange_service,
    )

    # Build Telegram Bot Application
    bot_app = create_bot_application(
        client=client,
        user_repo=user_repo,
        dca_repo=dca_repo,
        order_repo=order_repo,
        alert_repo=alert_repo,
        tx_repo=tx_repo,
        exchange_service=exchange_service,
        balance_service=balance_service,
        portfolio_service=portfolio_service,
        dca_service=dca_service,
        order_service=order_service,
        alert_service=alert_service,
        history_service=history_service,
        report_service=report_service,
    )

    # Setup Centralized Scheduler
    scheduler = BotScheduler(
        bot=bot_app.bot,
        report_service=report_service,
        dca_service=dca_service,
        alert_service=alert_service,
        order_repo=order_repo,
    )

    # Start scheduler when bot initializes
    async def post_init(application) -> None:
        scheduler.start()
        logger.info("Bot application initialized and scheduler started.")

    async def post_shutdown(application) -> None:
        scheduler.shutdown()
        await client.close()
        logger.info("Bot application and connections shut down cleanly.")

    bot_app.post_init = post_init
    bot_app.post_shutdown = post_shutdown

    logger.info(
        f"Bot starting... Trading mode: {'REAL' if settings.TRADING_ENABLED else 'SIMULATION/DRY-RUN'}"
    )
    bot_app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
