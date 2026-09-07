"""Contratos y providers intercambiables del advisor."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.modules.advisor.tools import ToolRegistry


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
