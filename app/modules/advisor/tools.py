"""Registro tipado de herramientas de lectura para el advisor."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError


class EmptyArguments(BaseModel):
    """Argumentos para una herramienta sin parámetros."""


class PositionArguments(BaseModel):
    ticker: str


class ExchangeRateArguments(BaseModel):
    source_currency: str
    dest_currency: str


class ToolExecutionError(RuntimeError):
    """Error seguro al validar o ejecutar una herramienta."""


ToolHandler = Callable[[BaseModel], Awaitable[Any]]
ArgumentsT = TypeVar("ArgumentsT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    arguments_model: type[BaseModel]
    handler: ToolHandler


class ToolRegistry:
    """Permite únicamente herramientas registradas y con argumentos validados."""

    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        arguments_model: type[ArgumentsT],
        handler: Callable[[ArgumentsT], Awaitable[Any]],
    ) -> None:
        """Registra una herramienta conservando su tipo concreto de argumentos.

        Args:
            name: Nombre público permitido para el provider.
            arguments_model: Modelo Pydantic que valida la entrada.
            handler: Operación de solo lectura para ese modelo concreto.

        Raises:
            ValueError: Si se intenta registrar una acción de trading.
        """
        if name == "execute_trade":
            raise ValueError("El advisor no puede registrar herramientas de trading.")

        async def validated_handler(arguments: BaseModel) -> Any:
            if not isinstance(arguments, arguments_model):
                raise ToolExecutionError(f"Argumentos inválidos para {name}.")
            return await handler(arguments)

        self._definitions[name] = ToolDefinition(name, arguments_model, validated_handler)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._definitions))

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        definition = self._definitions.get(name)
        if definition is None:
            raise ToolExecutionError(f"Herramienta no disponible: {name}")
        try:
            parsed = definition.arguments_model.model_validate(arguments)
        except ValidationError as error:
            raise ToolExecutionError(f"Argumentos inválidos para {name}.") from error
        try:
            return await definition.handler(parsed)
        except ToolExecutionError:
            raise
        except Exception as error:
            raise ToolExecutionError(f"No se pudo consultar {name}.") from error
