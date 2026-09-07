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


@pytest.mark.asyncio
async def test_gemini_provider_requires_api_key(monkeypatch):
    from app.modules.advisor.provider import AdvisorContext, AdvisorProviderUnavailableError, GeminiProvider
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    provider = GeminiProvider()
    with pytest.raises(AdvisorProviderUnavailableError, match="AI_API_KEY"):
        await provider.analyze(AdvisorContext("USD", "UTC", "hola"), ToolRegistry())


@pytest.mark.asyncio
async def test_gemini_provider_success(monkeypatch):
    import httpx

    from app.modules.advisor.provider import AdvisorContext, GeminiProvider

    monkeypatch.setattr(settings, "AI_API_KEY", "test-key-123")
    monkeypatch.setattr(settings, "AI_MODEL", "gemini-2.5-flash")

    mock_resp = {
        "candidates": [
            {"content": {"parts": [{"text": "<b>Análisis Gemini</b>: Cartera diversificada."}]}}
        ]
    }

    async def mock_post(url, **kwargs):
        return httpx.Response(200, json=mock_resp, request=httpx.Request("POST", url))

    client = httpx.AsyncClient()
    monkeypatch.setattr(client, "post", mock_post)

    provider = GeminiProvider(client=client)
    result = await provider.analyze(AdvisorContext("USD", "UTC", "como estoy?"), ToolRegistry())
    assert "Cartera diversificada" in result


@pytest.mark.asyncio
async def test_openai_provider_success(monkeypatch):
    import httpx

    from app.modules.advisor.provider import AdvisorContext, OpenAIProvider

    monkeypatch.setattr(settings, "AI_API_KEY", "test-key-openai")
    monkeypatch.setattr(settings, "AI_MODEL", "gpt-4o-mini")

    mock_resp = {
        "choices": [
            {"message": {"content": "<b>Análisis OpenAI</b>: Riesgo moderado."}}
        ]
    }

    async def mock_post(url, **kwargs):
        return httpx.Response(200, json=mock_resp, request=httpx.Request("POST", url))

    client = httpx.AsyncClient()
    monkeypatch.setattr(client, "post", mock_post)

    provider = OpenAIProvider(client=client)
    result = await provider.analyze(AdvisorContext("USD", "UTC", "evalua riesgo"), ToolRegistry())
    assert "Riesgo moderado" in result


def test_advisor_provider_selection(monkeypatch):
    from app.modules.advisor.provider import GeminiProvider, MockProvider, OpenAIProvider, WallsyncProvider
    from app.modules.advisor.service import AdvisorService

    monkeypatch.setattr(settings, "WALLSYNC_ENABLED", False)

    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
    assert isinstance(AdvisorService._provider_from_settings(), MockProvider)

    monkeypatch.setattr(settings, "AI_PROVIDER", "gemini")
    assert isinstance(AdvisorService._provider_from_settings(), GeminiProvider)

    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    assert isinstance(AdvisorService._provider_from_settings(), OpenAIProvider)

    monkeypatch.setattr(settings, "WALLSYNC_ENABLED", True)
    assert isinstance(AdvisorService._provider_from_settings(), WallsyncProvider)

