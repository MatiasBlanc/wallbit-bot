"""Servicio de análisis de solo lectura y herramientas financieras tipadas."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.advisor.provider import (
    AdvisorContext,
    AdvisorProviderUnavailableError,
    AIProvider,
    MockProvider,
    WallsyncProvider,
)
from app.modules.advisor.tools import (
    EmptyArguments,
    ExchangeRateArguments,
    PositionArguments,
    ToolRegistry,
)
from app.modules.alerts.service import AlertService
from app.modules.balance.service import BalanceService
from app.modules.dca.service import DCAService
from app.modules.history.service import HistoryService
from app.modules.portfolio.service import PortfolioService
from app.modules.reports.service import ReportService
from app.modules.settings.models import UserSettings


class AdvisorDisabledError(RuntimeError):
    """La feature de IA está desactivada por configuración."""


class AdvisorService:
    """Orquesta provider y servicios; nunca expone el cliente Wallbit al modelo."""

    def __init__(
        self,
        balance_service: BalanceService,
        portfolio_service: PortfolioService,
        report_service: ReportService,
        history_service: HistoryService,
        dca_service: DCAService,
        alert_service: AlertService,
        provider: AIProvider | None = None,
    ) -> None:
        self.balance_service = balance_service
        self.portfolio_service = portfolio_service
        self.report_service = report_service
        self.history_service = history_service
        self.dca_service = dca_service
        self.alert_service = alert_service
        self.provider = provider or self._provider_from_settings()

    @staticmethod
    def _provider_from_settings() -> AIProvider:
        if settings.WALLSYNC_ENABLED or settings.AI_PROVIDER.lower() == "wallsync":
            return WallsyncProvider()
        return MockProvider()

    def _build_tools(self, session: Session, user: UserSettings) -> ToolRegistry:
        registry = ToolRegistry()

        async def get_balance(_: EmptyArguments) -> dict[str, Any]:
            balance = await self.balance_service.get_balance(user.default_currency)
            return {
                "available_usd": balance.available_usd,
                "total_wealth_usd": balance.total_wealth_usd,
                "currency": user.default_currency,
                "converted_available": balance.converted_available,
            }

        async def get_portfolio(_: EmptyArguments) -> list[dict[str, Any]]:
            portfolio = await self.portfolio_service.get_portfolio(session=session, user_id=user.id)
            return [
                {
                    "ticker": position.ticker,
                    "quantity": position.shares,
                    "market_value": position.current_value,
                    "cost_basis": position.cost_basis,
                    "return_pct": position.roi_pct,
                }
                for position in portfolio.positions
            ]

        async def get_position(arguments: PositionArguments) -> dict[str, Any]:
            position = await self.portfolio_service.get_position(
                arguments.ticker, session=session, user_id=user.id
            )
            return {
                "ticker": position.ticker,
                "quantity": position.shares,
                "market_value": position.current_value,
                "cost_basis": position.cost_basis,
                "return_pct": position.roi_pct,
            }

        async def get_recent_transactions(_: EmptyArguments) -> list[dict[str, Any]]:
            items, _, _ = await self.history_service.get_history(session, user.id, limit=5)
            return [
                {"title": item.title, "amount_usd": item.amount_usd, "date": item.date_str, "status": item.status}
                for item in items
            ]

        async def get_dca_rules(_: EmptyArguments) -> list[dict[str, Any]]:
            rules = self.dca_service.list_active_rules(session, user.id, limit=20)
            return [
                {
                    "ticker": rule.ticker,
                    "amount_usd": rule.amount_usd,
                    "frequency": rule.frequency,
                    "weekday": rule.weekday,
                    "next_execution_at": rule.next_execution_at.isoformat(),
                }
                for rule in rules
            ]

        async def get_alerts(_: EmptyArguments) -> list[dict[str, Any]]:
            alerts = self.alert_service.list_user_alerts(session, user.id, limit=20)
            return [
                {
                    "symbol": alert.symbol,
                    "operator": alert.operator,
                    "target_value": alert.target_value,
                    "enabled": alert.enabled,
                    "triggered": alert.triggered,
                }
                for alert in alerts
            ]

        async def get_exchange_rate(arguments: ExchangeRateArguments) -> dict[str, Any]:
            rate = await self.report_service.exchange_service.get_rate(
                arguments.source_currency, arguments.dest_currency
            )
            return {
                "source_currency": arguments.source_currency.upper(),
                "dest_currency": arguments.dest_currency.upper(),
                "rate": rate,
            }

        async def get_report(_: EmptyArguments) -> dict[str, Any]:
            report = await self.report_service.generate_report(session, user)
            return {
                "available_balance_usd": report.available_balance_usd,
                "total_investments_usd": report.total_investments_usd,
                "total_gain_usd": report.total_gain_usd,
                "total_roi_pct": report.total_roi_pct,
                "best_position": report.best_position_ticker,
                "worst_position": report.worst_position_ticker,
            }

        registry.register("get_balance", EmptyArguments, get_balance)
        registry.register("get_portfolio", EmptyArguments, get_portfolio)
        registry.register("get_position", PositionArguments, get_position)
        registry.register("get_recent_transactions", EmptyArguments, get_recent_transactions)
        registry.register("get_dca_rules", EmptyArguments, get_dca_rules)
        registry.register("get_alerts", EmptyArguments, get_alerts)
        registry.register("get_exchange_rate", ExchangeRateArguments, get_exchange_rate)
        registry.register("get_report", EmptyArguments, get_report)
        return registry

    async def analyze(self, session: Session, user: UserSettings, query: str) -> str:
        """Analiza una consulta sin permitir mutaciones financieras."""
        if not settings.AI_ENABLED:
            raise AdvisorDisabledError("El análisis IA está desactivado en la configuración.")
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("Escribe una pregunta para analizar tu cartera.")
        context = AdvisorContext(currency=user.default_currency, timezone=user.timezone, query=clean_query)
        return await self.provider.analyze(context, self._build_tools(session, user))

    @staticmethod
    def provider_status() -> str:
        """Estado visible sin revelar configuración sensible."""
        if not settings.AI_ENABLED:
            return "🔴 Desactivada"
        if settings.WALLSYNC_ENABLED:
            return "🟢 Wallsync"
        return f"🟢 {settings.AI_PROVIDER}"


__all__ = ["AdvisorDisabledError", "AdvisorProviderUnavailableError", "AdvisorService"]
