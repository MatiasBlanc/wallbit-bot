"""Main application entry point for Wallbit Assistant Bot."""

import sys

from app.bot.application import create_bot_application
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.infrastructure.database.database import get_db_session, init_db
from app.infrastructure.scheduler.scheduler import BotScheduler
from app.infrastructure.wallbit.client import WallbitClient
from app.infrastructure.wallbit.health import WallbitHealth
from app.modules.advisor.service import AdvisorService
from app.modules.alerts.repository import AlertRepository
from app.modules.alerts.service import AlertService
from app.modules.auth.service import validate_multi_user_config
from app.modules.balance.service import BalanceService
from app.modules.dca.repository import DCARuleRepository
from app.modules.dca.service import DCAService
from app.modules.history.repository import LocalTransactionRepository
from app.modules.history.service import HistoryService
from app.modules.orders.repository import PendingOrderRepository
from app.modules.orders.service import OrderService
from app.modules.portfolio.service import PortfolioService
from app.modules.reports.service import ReportService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.exchange.providers import WallbitExchangeRateProvider
from app.shared.exchange.service import ExchangeRateService

setup_logging()
logger = get_logger("main")


def main() -> None:
    logger.info("Initializing Wallbit Assistant Bot...")

    validate_multi_user_config()

    # La instancia privada no puede funcionar sin sus tres credenciales obligatorias.
    missing_settings = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", settings.TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_ALLOWED_USER_ID", settings.TELEGRAM_ALLOWED_USER_ID),
            ("WALLBIT_API_KEY", settings.WALLBIT_API_KEY),
        )
        if not value
    ]
    if missing_settings:
        missing_names = ", ".join(missing_settings)
        logger.error("Faltan variables obligatorias: %s", missing_names)
        print(f"ERROR: faltan variables obligatorias en .env: {missing_names}")
        sys.exit(1)

    # Initialize Database
    logger.info("Setting up database tables...")
    init_db()

    # Instantiate HTTP Client
    client = WallbitClient(
        base_url=settings.WALLBIT_BASE_URL,
        api_key=settings.WALLBIT_API_KEY,
    )
    health = WallbitHealth(client)

    # Instantiate Repositories
    user_repo = UserSettingsRepository()
    dca_repo = DCARuleRepository()
    order_repo = PendingOrderRepository()
    with get_db_session() as session:
        interrupted_orders = order_repo.recover_interrupted_orders(session)
    if interrupted_orders:
        logger.warning(
            "%s órdenes interrumpidas pasaron a verificación manual.",
            interrupted_orders,
        )
    alert_repo = AlertRepository()
    tx_repo = LocalTransactionRepository()

    # Instantiate Services
    wallbit_rate_provider = WallbitExchangeRateProvider(client)
    exchange_service = ExchangeRateService(
        primary_provider=wallbit_rate_provider,
        cache_ttl_seconds=int(settings.FX_CACHE_TTL_SECONDS),
    )
    balance_service = BalanceService(client=client, exchange_service=exchange_service)
    portfolio_service = PortfolioService(client=client, tx_repo=tx_repo)
    order_service = OrderService(
        order_repo=order_repo,
        tx_repo=tx_repo,
        client=client,
        balance_service=balance_service,
    )
    dca_service = DCAService(
        dca_repo=dca_repo,
        order_service=order_service,
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
    advisor_service = AdvisorService(
        balance_service=balance_service,
        portfolio_service=portfolio_service,
        report_service=report_service,
        history_service=history_service,
        dca_service=dca_service,
        alert_service=alert_service,
    )

    # Build Telegram Bot Application
    bot_app = create_bot_application(
        client=client,
        user_repo=user_repo,
        balance_service=balance_service,
        portfolio_service=portfolio_service,
        dca_service=dca_service,
        order_service=order_service,
        alert_service=alert_service,
        history_service=history_service,
        report_service=report_service,
        advisor_service=advisor_service,
    )

    # Setup Centralized Scheduler
    scheduler = BotScheduler(
        bot=bot_app.bot,
        report_service=report_service,
        dca_service=dca_service,
        alert_service=alert_service,
        order_repo=order_repo,
        health=health,
    )

    # Start scheduler when bot initializes
    async def post_init(application) -> None:
        application.bot_data["wallbit_health"] = health
        scheduler.start()
        application.create_task(health.refresh())
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
    bot_app.run_polling(drop_pending_updates=True, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
