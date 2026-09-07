"""Construcción de la aplicación de Telegram."""

import asyncio

from telegram.ext import Application

from app.bot.error_handler import error_handler
from app.bot.processor import PerUserUpdateProcessor
from app.bot.registry import register_handlers
from app.core.config import settings
from app.infrastructure.wallbit.client import WallbitClient
from app.modules.advisor.service import AdvisorService
from app.modules.alerts.service import AlertService
from app.modules.balance.service import BalanceService
from app.modules.dca.service import DCAService
from app.modules.history.service import HistoryService
from app.modules.orders.service import OrderService
from app.modules.portfolio.service import PortfolioService
from app.modules.reports.service import ReportService
from app.modules.settings.repository import UserSettingsRepository


def create_bot_application(
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
) -> Application:
    """Construye el bot sin iniciarlo ni realizar solicitudes de red.

    Args:
        client: Cliente Wallbit para diagnóstico de conexión.
        user_repo: Repositorio de preferencias de usuario.
        balance_service: Servicio de consulta de saldos.
        portfolio_service: Servicio de consulta de inversiones.
        dca_service: Servicio de reglas de compra recurrente.
        order_service: Servicio de confirmación de órdenes.
        alert_service: Servicio de alertas de precio y divisa.
        history_service: Servicio de historial de movimientos.
        report_service: Servicio de reportes financieros.
        advisor_service: Servicio de análisis opcional y de solo lectura.

    Returns:
        Aplicación con rutas y manejador global de errores registrados.

    Raises:
        telegram.error.InvalidToken: Si el token configurado no es válido.
    """
    application = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(PerUserUpdateProcessor(8) if settings.MULTI_USER_ENABLED else False)
        .connection_pool_size(8)
        .update_queue(asyncio.Queue(maxsize=100))
        .build()
    )
    register_handlers(
        application, client, user_repo, balance_service, portfolio_service,
        dca_service, order_service, alert_service, history_service, report_service, advisor_service,
    )
    application.add_error_handler(error_handler)
    return application
