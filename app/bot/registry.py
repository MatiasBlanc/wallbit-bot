"""Registro de rutas de Telegram por módulo funcional."""

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.bot.commands import get_orders_handler, get_start_handler, get_status_handler
from app.core.config import settings
from app.infrastructure.wallbit.client import WallbitClient
from app.modules.advisor.handler import get_advisor_callbacks, get_advisor_handler
from app.modules.advisor.service import AdvisorService
from app.modules.alerts.callbacks import get_alert_callbacks
from app.modules.alerts.conversation import get_alert_conversation_handler
from app.modules.alerts.handler import get_alerts_handler
from app.modules.alerts.service import AlertService
from app.modules.auth.commands import login_command, logout_command
from app.modules.balance.handler import get_balance_handler
from app.modules.balance.service import BalanceService
from app.modules.dca.callbacks import get_dca_callbacks
from app.modules.dca.conversation import get_dca_conversation_handler
from app.modules.dca.handler import get_dca_handler
from app.modules.dca.service import DCAService
from app.modules.history.callbacks import get_history_callback
from app.modules.history.handler import get_history_handler
from app.modules.history.service import HistoryService
from app.modules.orders.callbacks import get_order_callbacks, get_order_reconciliation_callback
from app.modules.orders.service import OrderService
from app.modules.portfolio.handler import get_investments_handler
from app.modules.portfolio.service import PortfolioService
from app.modules.reports.handler import get_report_handler
from app.modules.reports.service import ReportService
from app.modules.settings.callbacks import get_config_callbacks
from app.modules.settings.conversation import get_config_time_conversation_handler
from app.modules.settings.handler import get_config_handler
from app.modules.settings.keyboards import MAIN_MENU_LABELS
from app.modules.settings.repository import UserSettingsRepository


def register_balance_handlers(
    application: Application, service: BalanceService, user_repo: UserSettingsRepository,
) -> None:
    """Registra la consulta de saldos.

    Args:
        application: Aplicación que recibe las rutas.
        service: Servicio de saldos.
        user_repo: Repositorio de preferencias.

    Returns:
        None.
    """
    application.add_handler(CommandHandler("saldo", get_balance_handler(service, user_repo)))


def register_portfolio_handlers(
    application: Application, service: PortfolioService, user_repo: UserSettingsRepository,
) -> None:
    """Registra la consulta de inversiones.

    Args:
        application: Aplicación que recibe las rutas.
        service: Servicio de portafolio.
        user_repo: Repositorio de preferencias.

    Returns:
        None.
    """
    application.add_handler(CommandHandler("inv", get_investments_handler(service, user_repo)))


def register_dca_handlers(
    application: Application, service: DCAService, user_repo: UserSettingsRepository,
) -> None:
    """Registra el menú y callbacks DCA después de las conversaciones.

    Args:
        application: Aplicación que recibe las rutas.
        service: Servicio de reglas DCA.
        user_repo: Repositorio de preferencias.

    Returns:
        None.
    """
    application.add_handler(CommandHandler("dca", get_dca_handler(service, user_repo)))
    callbacks = get_dca_callbacks(service, user_repo)
    for action, pattern in (
        ("active", r"^dca_menu:active(?::[1-9]\d*)?$"),
        ("paused", r"^dca_menu:paused(?::[1-9]\d*)?$"),
        ("back", r"^dca_menu:back$"),
        ("close", r"^dca_menu:close$"),
        ("pause", r"^dca_pause:"),
        ("resume", r"^dca_resume:"),
        ("delete", r"^dca_delete:"),
    ):
        application.add_handler(CallbackQueryHandler(callbacks[action], pattern=pattern))


def register_alert_handlers(
    application: Application, service: AlertService, user_repo: UserSettingsRepository,
) -> None:
    """Registra el menú y callbacks de alertas después de las conversaciones.

    Args:
        application: Aplicación que recibe las rutas.
        service: Servicio de alertas.
        user_repo: Repositorio de preferencias.

    Returns:
        None.
    """
    application.add_handler(CommandHandler("alerta", get_alerts_handler(user_repo)))
    callbacks = get_alert_callbacks(service, user_repo)
    for action, pattern in (
        ("list", r"^alert_menu:list(?::[1-9]\d*)?$"),
        ("back", r"^alert_menu:back$"),
        ("close", r"^alert_menu:close$"),
        ("delete", r"^alert_delete:"),
    ):
        application.add_handler(CallbackQueryHandler(callbacks[action], pattern=pattern))


def register_order_handlers(
    application: Application, service: OrderService, user_repo: UserSettingsRepository,
) -> None:
    """Registra la confirmación y omisión de órdenes.

    Args:
        application: Aplicación que recibe las rutas.
        service: Servicio de órdenes.
        user_repo: Repositorio de preferencias.

    Returns:
        None.
    """
    confirm_callback, skip_callback = get_order_callbacks(service, user_repo)
    application.add_handler(CallbackQueryHandler(confirm_callback, pattern=r"^order_confirm:"))
    application.add_handler(CallbackQueryHandler(skip_callback, pattern=r"^order_skip:"))
    application.add_handler(
        CallbackQueryHandler(
            get_order_reconciliation_callback(service, user_repo),
            pattern=r"^order_reconcile:(?:executed|failed):[1-9]\d*$",
        )
    )


def register_history_handlers(
    application: Application, service: HistoryService, user_repo: UserSettingsRepository,
) -> None:
    """Registra el historial y su paginación.

    Args:
        application: Aplicación que recibe las rutas.
        service: Servicio de historial.
        user_repo: Repositorio de preferencias.

    Returns:
        None.
    """
    application.add_handler(CommandHandler("historial", get_history_handler(service, user_repo)))
    application.add_handler(CallbackQueryHandler(get_history_callback(service, user_repo), pattern=r"^history_page:"))


def register_report_handlers(
    application: Application, service: ReportService, user_repo: UserSettingsRepository,
) -> None:
    """Registra el reporte manual.

    Args:
        application: Aplicación que recibe las rutas.
        service: Servicio de reportes.
        user_repo: Repositorio de preferencias.

    Returns:
        None.
    """
    application.add_handler(CommandHandler("reporte", get_report_handler(service, user_repo)))


def register_settings_handlers(
    application: Application, client: WallbitClient, user_repo: UserSettingsRepository,
) -> None:
    """Registra el menú y callbacks de configuración después de las conversaciones.

    Args:
        application: Aplicación que recibe las rutas.
        client: Cliente Wallbit para diagnóstico.
        user_repo: Repositorio de preferencias.

    Returns:
        None.
    """
    application.add_handler(CommandHandler("config", get_config_handler(user_repo)))
    callbacks = get_config_callbacks(client, user_repo)
    for action, pattern in (
        ("currency", r"^config:currency$"),
        ("set_currency", r"^set_currency:"),
        ("timezone", r"^config:timezone$"),
        ("set_timezone", r"^set_tz:"),
        ("toggle_alerts", r"^config:toggle_alerts$"),
        ("status", r"^config:status$"),
        ("back", r"^config:back$"),
        ("close", r"^config:close$"),
    ):
        application.add_handler(CallbackQueryHandler(callbacks[action], pattern=pattern))


def register_handlers(
    application: Application,
    client: WallbitClient,
    user_repo: UserSettingsRepository,
    balance_service: BalanceService,
    portfolio_service: PortfolioService,
    dca_service: DCAService,
    order_service: OrderService,
    alert_service: AlertService,
    history_service: HistoryService,
    report_service: ReportService,
    advisor_service: AdvisorService | None = None,
) -> None:
    """Registra los módulos conservando la prioridad de las conversaciones.

    Args:
        application: Aplicación que recibe todas las rutas.
        client: Cliente Wallbit para diagnóstico.
        user_repo: Repositorio de preferencias.
        balance_service: Servicio de saldos.
        portfolio_service: Servicio de portafolio.
        dca_service: Servicio de reglas DCA.
        order_service: Servicio de órdenes.
        alert_service: Servicio de alertas.
        history_service: Servicio de historial.
        report_service: Servicio de reportes.

    Returns:
        None.
    """
    # Un grupo previo permite salir incluso durante una conversación de otro módulo.
    if settings.MULTI_USER_ENABLED:
        application.add_handler(CommandHandler("login", login_command), group=-1)
        application.add_handler(CommandHandler("logout", logout_command), group=-1)

    # En el mismo grupo, Telegram utiliza el primer handler que acepta el update.
    application.add_handler(get_dca_conversation_handler(dca_service, user_repo))
    application.add_handler(get_alert_conversation_handler(alert_service, user_repo))
    application.add_handler(get_config_time_conversation_handler(user_repo))

    application.add_handler(CommandHandler("start", get_start_handler(client, user_repo)))
    application.add_handler(CommandHandler(["estado", "status"], get_status_handler()))
    application.add_handler(CommandHandler("ordenes", get_orders_handler(order_service, user_repo)))
    register_balance_handlers(application, balance_service, user_repo)
    register_portfolio_handlers(application, portfolio_service, user_repo)
    register_report_handlers(application, report_service, user_repo)
    register_history_handlers(application, history_service, user_repo)
    register_dca_handlers(application, dca_service, user_repo)
    register_alert_handlers(application, alert_service, user_repo)
    register_settings_handlers(application, client, user_repo)
    register_order_handlers(application, order_service, user_repo)
    if advisor_service is not None:
        application.add_handler(CommandHandler("analizar", get_advisor_handler(advisor_service, user_repo)))
        application.add_handler(
            CallbackQueryHandler(
                get_advisor_callbacks(advisor_service, user_repo),
                pattern=r"^advisor:",
            )
        )

    menu_handlers = {
        "saldo": get_balance_handler(balance_service, user_repo),
        "inv": get_investments_handler(portfolio_service, user_repo),
        "dca": get_dca_handler(dca_service, user_repo),
        "alerta": get_alerts_handler(user_repo),
        "historial": get_history_handler(history_service, user_repo),
        "reporte": get_report_handler(report_service, user_repo),
        "config": get_config_handler(user_repo),
    }
    if advisor_service is not None:
        menu_handlers["analizar"] = get_advisor_handler(advisor_service, user_repo)

    async def route_menu(update, context):
        if not update.effective_message:
            return
        command = MAIN_MENU_LABELS.get(update.effective_message.text)
        handler = menu_handlers.get(command)
        if handler is not None:
            await handler(update, context)

    application.add_handler(MessageHandler(filters.Text(tuple(MAIN_MENU_LABELS)), route_menu))
