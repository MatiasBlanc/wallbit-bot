import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

import httpx

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.modules.advisor.tools import ToolRegistry

logger = get_logger(__name__)

SYSTEM_INSTRUCTION = (
    "Eres el Asesor Financiero del Wallbit Assistant Bot. "
    "Tu rol es analizar la cartera, saldos y movimientos del usuario de manera analítica, objetiva y concisa. "
    "REGLAS OBLIGATORIAS:\n"
    "1. NO tienes capacidad de ejecutar operaciones ni de trading. Solo eres analista de lectura.\n"
    "2. No des consejos de inversión vinculantes ni promesas de rendimiento; presenta pros, contras, diversificación y riesgo.\n"
    "3. Usa formato Telegram HTML: <b>negrita</b>, <i>cursiva</i>, <code>código</code>, listas con guiones.\n"
    "4. Responde en español, de forma clara, directa y estructurada."
)


@dataclass(frozen=True, slots=True)
class AdvisorContext:
    """Contexto mínimo enviado al provider, sin JSON crudo ni secretos."""

    currency: str
    timezone: str
    query: str


class AIProvider(Protocol):
    """Provider de análisis sin acceso directo a Wallbit ni a órdenes."""

    async def analyze(self, context: AdvisorContext, tools: "ToolRegistry") -> str:
        """Genera un análisis usando exclusivamente las herramientas registradas."""


class AdvisorProviderUnavailableError(RuntimeError):
    """El provider solicitado no tiene una integración programática configurada."""


async def _gather_financial_summary(tools: "ToolRegistry") -> dict[str, Any]:
    """Recopila datos financieros de solo lectura de forma segura."""
    data: dict[str, Any] = {}
    for tool_name in ("get_report", "get_balance", "get_portfolio", "get_dca_rules", "get_alerts"):
        try:
            data[tool_name] = await tools.execute(tool_name, {})
        except Exception as err:
            logger.debug(f"Could not fetch tool {tool_name} for advisor prompt: {err}")
            data[tool_name] = None
    return data


def _build_user_prompt(context: AdvisorContext, financial_data: dict[str, Any]) -> str:
    """Construye el texto de usuario con el contexto financiero formateado."""
    return (
        f"Contexto del usuario:\n"
        f"- Moneda preferida: {context.currency}\n"
        f"- Zona horaria: {context.timezone}\n\n"
        f"Datos financieros actuales:\n"
        f"{json.dumps(financial_data, ensure_ascii=False, indent=2, default=str)}\n\n"
        f"Consulta del usuario:\n"
        f"{context.query}"
    )


class MockProvider:
    """Provider determinista para desarrollo y tests; no simula una recomendación."""

    async def analyze(self, context: AdvisorContext, tools: "ToolRegistry") -> str:
        report = await tools.execute("get_report", {})
        return (
            "📊 <b>Datos</b>\n"
            f"{report}\n\n"
            "🤖 <b>Análisis</b>\n"
            "Este resultado proviene del provider simulado. Configura un provider de IA real "
            "si quieres análisis en lenguaje natural."
        )


class WallsyncProvider:
    """Punto de extensión para Wallsync sin inventar endpoints ni automatizar su web."""

    async def analyze(self, context: AdvisorContext, tools: "ToolRegistry") -> str:
        raise AdvisorProviderUnavailableError(
            "Wallsync no tiene una integración programática configurada en esta instancia."
        )


class GeminiProvider:
    """Proveedor de IA usando Google Gemini API (REST)."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def analyze(self, context: AdvisorContext, tools: "ToolRegistry") -> str:
        api_key = settings.AI_API_KEY
        if not api_key:
            raise AdvisorProviderUnavailableError(
                "AI_API_KEY no está configurada para el provider Gemini. "
                "Define AI_API_KEY en tu archivo .env para activarlo."
            )

        model = settings.AI_MODEL or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        financial_data = await _gather_financial_summary(tools)
        user_prompt = _build_user_prompt(context, financial_data)

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 1024,
            },
        }

        async def _send(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(url, params={"key": api_key}, json=payload, timeout=30.0)

        try:
            if self._client:
                response = await _send(self._client)
            else:
                async with httpx.AsyncClient() as client:
                    response = await _send(client)

            if response.status_code != 200:
                logger.error(f"Gemini API returned status {response.status_code}")
                raise AdvisorProviderUnavailableError(
                    f"Error de comunicación con Gemini (código HTTP {response.status_code})."
                )

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return "🤖 No se pudo obtener respuesta del modelo Gemini."

            parts = candidates[0].get("content", {}).get("parts", [])
            if parts and "text" in parts[0]:
                return parts[0]["text"]
            return "🤖 Respuesta vacía recibida de Gemini."

        except (httpx.TimeoutException, httpx.NetworkError) as err:
            logger.warning(f"Network error contacting Gemini API: {err}")
            raise AdvisorProviderUnavailableError(
                "Tiempo de espera agotado al conectar con el servicio de IA de Gemini."
            ) from err


class OpenAIProvider:
    """Proveedor de IA compatible con OpenAI API y otros endpoints compatibles."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def analyze(self, context: AdvisorContext, tools: "ToolRegistry") -> str:
        api_key = settings.AI_API_KEY
        if not api_key:
            raise AdvisorProviderUnavailableError(
                "AI_API_KEY no está configurada para el provider OpenAI. "
                "Define AI_API_KEY en tu archivo .env para activarlo."
            )

        base_url = settings.AI_BASE_URL.rstrip("/") if settings.AI_BASE_URL else "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"
        model = settings.AI_MODEL or "gpt-4o-mini"

        financial_data = await _gather_financial_summary(tools)
        user_prompt = _build_user_prompt(context, financial_data)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 1024,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async def _send(client: httpx.AsyncClient) -> httpx.Response:
            return await client.post(url, headers=headers, json=payload, timeout=30.0)

        try:
            if self._client:
                response = await _send(self._client)
            else:
                async with httpx.AsyncClient() as client:
                    response = await _send(client)

            if response.status_code != 200:
                logger.error(f"OpenAI API returned status {response.status_code}")
                raise AdvisorProviderUnavailableError(
                    f"Error de comunicación con OpenAI (código HTTP {response.status_code})."
                )

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return "🤖 No se pudo obtener respuesta del modelo OpenAI."

            message = choices[0].get("message", {})
            return message.get("content", "🤖 Respuesta vacía de OpenAI.")

        except (httpx.TimeoutException, httpx.NetworkError) as err:
            logger.warning(f"Network error contacting OpenAI API: {err}")
            raise AdvisorProviderUnavailableError(
                "Tiempo de espera agotado al conectar con el servicio de IA de OpenAI."
            ) from err
