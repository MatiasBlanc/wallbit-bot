"""Telegram bot setup and handler registration."""

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from app.bot.callbacks.alert_callbacks import get_alert_callbacks
from app.bot.callbacks.config_callbacks import get_config_callbacks
from app.bot.callbacks.dca_callbacks import get_dca_callbacks
from app.bot.callbacks.history_callbacks import get_history_callback
from app.bot.callbacks.order_callbacks import get_order_callbacks
from app.bot.conversations.alert_conv import get_alert_conversation_handler
from app.bot.conversations.config_conv import get_config_time_conversation_handler
from app.bot.conversations.dca_conv import get_dca_conversation_handler
from app.bot.handlers.alerts import get_alerts_handler
from app.bot.handlers.balance import get_balance_handler
from app.bot.handlers.config import get_config_handler
from app.bot.handlers.dca import get_dca_handler
from app.bot.handlers.history import get_history_handler
from app.bot.handlers.investments import get_investments_handler
from app.bot.handlers.report import get_report_handler
from app.bot.handlers.start import get_start_handler
from app.core.config import settings
from app.core.logging import get_logger
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
)
from app.services.history_service import HistoryService
from app.services.order_service import OrderService
from app.services.portfolio_service import PortfolioService
from app.services.report_service import ReportService
from app.wallbit.client import WallbitClient

logger = get_logger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error without exposing secrets to users."""
    logger.error("Exception while handling an update:", exc_info=context.error)


def create_bot_application(
    client: WallbitClient,
    user_repo: UserSettingsRepository,
    dca_repo: DCARuleRepository,
    order_repo: PendingOrderRepository,
    alert_repo: AlertRepository,
    tx_repo: LocalTransactionRepository,
    exchange_service: ExchangeRateService,
    balance_service: BalanceService,
    portfolio_service: PortfolioService,
    dca_service: DCAService,
    order_service: OrderService,
    alert_service: AlertService,
    history_service: HistoryService,
    report_service: ReportService,
) -> Application:
    """Build and configure the Telegram application with all routes and middleware."""
    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # --- Handlers ---
    start_handler = get_start_handler(client, user_repo)
    balance_handler = get_balance_handler(balance_service, user_repo)
    inv_handler = get_investments_handler(portfolio_service, user_repo)
    report_handler = get_report_handler(report_service, user_repo)
    history_handler = get_history_handler(history_service, user_repo)
    dca_handler = get_dca_handler(dca_service, user_repo)
    alerts_handler = get_alerts_handler(user_repo)
    config_handler = get_config_handler(user_repo)

    # --- Conversations ---
    dca_conv = get_dca_conversation_handler(dca_service, user_repo)
    alert_conv = get_alert_conversation_handler(alert_service, user_repo)
    config_time_conv = get_config_time_conversation_handler(user_repo)

    # Add conversations FIRST so their states capture messages properly
    app.add_handler(dca_conv)
    app.add_handler(alert_conv)
    app.add_handler(config_time_conv)

    # Add Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("saldo", balance_handler))
    app.add_handler(CommandHandler("inv", inv_handler))
    app.add_handler(CommandHandler("reporte", report_handler))
    app.add_handler(CommandHandler("historial", history_handler))
    app.add_handler(CommandHandler("dca", dca_handler))
    app.add_handler(CommandHandler("alerta", alerts_handler))
    app.add_handler(CommandHandler("config", config_handler))

    # --- Callbacks ---
    confirm_cb, skip_cb = get_order_callbacks(order_service, user_repo)
    app.add_handler(CallbackQueryHandler(confirm_cb, pattern=r"^order_confirm:"))
    app.add_handler(CallbackQueryHandler(skip_cb, pattern=r"^order_skip:"))

    dca_cbs = get_dca_callbacks(dca_service, user_repo)
    app.add_handler(CallbackQueryHandler(dca_cbs["active"], pattern=r"^dca_menu:active$"))
    app.add_handler(CallbackQueryHandler(dca_cbs["paused"], pattern=r"^dca_menu:paused$"))
    app.add_handler(CallbackQueryHandler(dca_cbs["back"], pattern=r"^dca_menu:back$"))
    app.add_handler(CallbackQueryHandler(dca_cbs["close"], pattern=r"^dca_menu:close$"))
    app.add_handler(CallbackQueryHandler(dca_cbs["pause"], pattern=r"^dca_pause:"))
    app.add_handler(CallbackQueryHandler(dca_cbs["resume"], pattern=r"^dca_resume:"))
    app.add_handler(CallbackQueryHandler(dca_cbs["delete"], pattern=r"^dca_delete:"))

    alert_cbs = get_alert_callbacks(alert_service, user_repo)
    app.add_handler(CallbackQueryHandler(alert_cbs["list"], pattern=r"^alert_menu:list$"))
    app.add_handler(CallbackQueryHandler(alert_cbs["back"], pattern=r"^alert_menu:back$"))
    app.add_handler(CallbackQueryHandler(alert_cbs["close"], pattern=r"^alert_menu:close$"))
    app.add_handler(CallbackQueryHandler(alert_cbs["delete"], pattern=r"^alert_delete:"))

    hist_cb = get_history_callback(history_service, user_repo)
    app.add_handler(CallbackQueryHandler(hist_cb, pattern=r"^history_page:"))

    cfg_cbs = get_config_callbacks(client, user_repo)
    app.add_handler(CallbackQueryHandler(cfg_cbs["currency"], pattern=r"^config:currency$"))
    app.add_handler(CallbackQueryHandler(cfg_cbs["set_currency"], pattern=r"^set_currency:"))
    app.add_handler(CallbackQueryHandler(cfg_cbs["timezone"], pattern=r"^config:timezone$"))
    app.add_handler(CallbackQueryHandler(cfg_cbs["set_timezone"], pattern=r"^set_tz:"))
    app.add_handler(CallbackQueryHandler(cfg_cbs["toggle_alerts"], pattern=r"^config:toggle_alerts$"))
    app.add_handler(CallbackQueryHandler(cfg_cbs["status"], pattern=r"^config:status$"))
    app.add_handler(CallbackQueryHandler(cfg_cbs["back"], pattern=r"^config:back$"))
    app.add_handler(CallbackQueryHandler(cfg_cbs["close"], pattern=r"^config:close$"))

    # Global error handler
    app.add_error_handler(error_handler)

    return app
