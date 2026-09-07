"""Pruebas del advisor opcional y de sus límites de seguridad."""

import pytest

from app.core.config import settings
from app.modules.advisor.provider import MockProvider
from app.modules.advisor.service import AdvisorDisabledError, AdvisorService
from app.modules.advisor.tools import EmptyArguments, ToolExecutionError, ToolRegistry


def make_advisor(balance_service, portfolio_service, report_service, history_service, dca_service, alert_service):
    return AdvisorService(
        balance_service=balance_service,
        portfolio_service=portfolio_service,
        report_service=report_service,
        history_service=history_service,
        dca_service=dca_service,
        alert_service=alert_service,
        provider=MockProvider(),
    )


@pytest.mark.asyncio
async def test_advisor_disabled_does_not_query_financial_services(
    balance_service, portfolio_service, report_service, history_service, dca_service, alert_service,
    db_session, test_user, monkeypatch,
):
    monkeypatch.setattr(settings, "AI_ENABLED", False)
    advisor = make_advisor(
        balance_service, portfolio_service, report_service, history_service, dca_service, alert_service,
    )

    with pytest.raises(AdvisorDisabledError):
        await advisor.analyze(db_session, test_user, "Resume mi cartera")



@pytest.mark.asyncio
async def test_mock_advisor_uses_typed_read_tools_and_cannot_trade(
    balance_service, portfolio_service, report_service, history_service, dca_service, alert_service,
    db_session, test_user, monkeypatch,
):
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    advisor = make_advisor(
        balance_service, portfolio_service, report_service, history_service, dca_service, alert_service,
    )

    result = await advisor.analyze(db_session, test_user, "Resume mi cartera")

    assert "Datos" in result
    registry = advisor._build_tools(db_session, test_user)
    assert "execute_trade" not in registry.names()
    with pytest.raises(ToolExecutionError):
        await registry.execute("execute_trade", {})


def test_tool_registry_rejects_trade_registration():
    registry = ToolRegistry()

    async def handler(_: EmptyArguments) -> None:
        return None

    with pytest.raises(ValueError, match="trading"):
        registry.register("execute_trade", EmptyArguments, handler)
