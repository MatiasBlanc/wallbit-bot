"""Asynchronous Wallbit Public API client."""

import asyncio
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.identity import current_identity
from app.core.logging import get_logger
from app.infrastructure.wallbit.exceptions import (
    ExchangeRateUnavailableError,
    InsufficientFundsError,
    InvalidTickerError,
    OrderExecutionError,
    WallbitApiException,
    WallbitAuthenticationError,
    WallbitForbiddenError,
    WallbitKYCRequiredError,
    WallbitNotFoundError,
    WallbitRateLimitError,
    WallbitUnavailableError,
    WallbitUnexpectedResponseError,
    WallbitValidationError,
)
from app.infrastructure.wallbit.schemas.balance import (
    CheckingBalanceItem,
    CheckingBalanceResponse,
    StockBalanceItem,
    StocksBalanceResponse,
)
from app.infrastructure.wallbit.schemas.orders import (
    ExchangeRateData,
    ExchangeRateResponse,
    TradeRequest,
    TradeResponse,
    TradeResult,
)
from app.infrastructure.wallbit.schemas.portfolio import (
    AssetDetails,
    AssetResponse,
    AssetsListResponse,
)
from app.infrastructure.wallbit.schemas.transactions import (
    TransactionsData,
    TransactionsResponse,
)

logger = get_logger(__name__)
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class WallbitClient:
    """HTTP client for Wallbit public API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 15.0,
        max_concurrent_requests: int | None = None,
    ):
        self.base_url = (base_url or settings.WALLBIT_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.WALLBIT_API_KEY
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self.max_concurrent_requests = (
            settings.WALLBIT_MAX_CONCURRENT_REQUESTS if max_concurrent_requests is None else max_concurrent_requests
        )
        if self.max_concurrent_requests < 1:
            raise ValueError("El límite de solicitudes debe ser positivo.")
        self._request_slots = asyncio.Semaphore(self.max_concurrent_requests)

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            # La autenticación es por API key: no propagar cookies entre cuentas.
            "Cookie": "",
        }
        if settings.MULTI_USER_ENABLED:
            identity = current_identity.get()
            if identity is None:
                raise WallbitAuthenticationError("Inicia sesión con /login antes de consultar Wallbit.")
            headers["X-API-Key"] = identity.api_key.get_secret_value()
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                # El pool se comparte; las credenciales se asignan a cada solicitud.
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=self.max_concurrent_requests,
                    max_keepalive_connections=self.max_concurrent_requests,
                ),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "WallbitClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    @staticmethod
    def _parse_json(response: httpx.Response) -> Any:
        """Convierte una respuesta en JSON sin filtrar su contenido en errores."""
        try:
            return response.json()
        except (TypeError, ValueError) as exc:
            raise WallbitUnexpectedResponseError() from exc

    def _parse_model(self, schema: type[SchemaT], response: httpx.Response) -> SchemaT:
        try:
            return schema.model_validate(self._parse_json(response))
        except ValidationError as exc:
            raise WallbitUnexpectedResponseError() from exc

    def _handle_error_response(self, response: httpx.Response) -> None:
        status = response.status_code
        try:
            body = response.json()
            message = body.get("message") if isinstance(body, dict) else None
            errors = body.get("errors") if isinstance(body, dict) else None
            if not isinstance(message, str) or not message.strip():
                message = "Error de Wallbit"
        except (TypeError, ValueError):
            message = "Wallbit devolvió una respuesta de error no válida."
            errors = None

        if status == 401:
            raise WallbitAuthenticationError(details=message)
        elif status == 403:
            raise WallbitForbiddenError(details=message)
        elif status == 404:
            raise WallbitNotFoundError(details=message)
        elif status == 412:
            raise WallbitKYCRequiredError(details=message)
        elif status == 422:
            raise WallbitValidationError(details=f"{message} - {errors}" if errors else message)
        elif status == 429:
            retry_after_hdr = response.headers.get("Retry-After")
            retry_after = int(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else 5
            raise WallbitRateLimitError(retry_after=retry_after, message=message)
        elif status == 400:
            if "insufficient" in message.lower() or "funds" in message.lower():
                raise InsufficientFundsError(details=message)
            raise WallbitApiException(user_message=message, status_code=400, details=message)
        elif status >= 500:
            raise WallbitUnavailableError(details=message, status_code=status)
        else:
            raise WallbitApiException(user_message=message, status_code=status, details=message)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        max_retries: int = 2,
    ) -> httpx.Response:
        headers = self._get_headers()
        client = await self.get_client()
        is_idempotent = method.upper() in ["GET", "HEAD", "OPTIONS"]

        for attempt in range(max_retries + 1):
            try:
                # El límite es global al cliente; el backoff no retiene un cupo.
                async with self._request_slots:
                    response = await client.request(
                        method=method,
                        url=path,
                        params=params,
                        json=json_data,
                        headers=headers,
                    )
                if response.status_code == 429 and attempt < max_retries and is_idempotent:
                    retry_after_hdr = response.headers.get("Retry-After")
                    delay = int(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else 2 ** (attempt + 1)
                    logger.warning(f"Rate limited by Wallbit (429). Retrying after {delay}s...")
                    await asyncio.sleep(delay)
                    continue

                if not response.is_success:
                    self._handle_error_response(response)
                return response

            except httpx.NetworkError as exc:
                if attempt < max_retries and is_idempotent:
                    delay = 2 ** attempt
                    logger.warning(
                        "Network error connecting to Wallbit; retrying after %ss (%s).",
                        delay,
                        type(exc).__name__,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error("Wallbit connection failed: %s", type(exc).__name__)
                raise WallbitUnavailableError() from exc

        raise WallbitUnavailableError("Max retry attempts reached for Wallbit API")

    # --- Endpoints ---

    async def check_connection(self) -> bool:
        """Verify API key and connectivity to Wallbit."""
        if not settings.MULTI_USER_ENABLED and not self.api_key:
            return False
        try:
            await self.get_checking_balance()
            return True
        except (WallbitAuthenticationError, WallbitForbiddenError):
            return False
        except Exception as e:
            logger.warning(f"check_connection encountered error: {e}")
            return False

    async def get_checking_balance(self) -> list[CheckingBalanceItem]:
        """GET /api/public/v1/balance/checking"""
        resp = await self._request("GET", "/api/public/v1/balance/checking")
        parsed = self._parse_model(CheckingBalanceResponse, resp)
        return parsed.data

    async def get_stocks_balance(self) -> list[StockBalanceItem]:
        """GET /api/public/v1/balance/stocks"""
        resp = await self._request("GET", "/api/public/v1/balance/stocks")
        parsed = self._parse_model(StocksBalanceResponse, resp)
        return parsed.data

    async def get_asset(self, symbol: str) -> AssetDetails:
        """GET /api/public/v1/assets/{symbol}"""
        try:
            resp = await self._request("GET", f"/api/public/v1/assets/{symbol.upper()}")
            parsed = self._parse_model(AssetResponse, resp)
            return parsed.data
        except WallbitNotFoundError:
            raise InvalidTickerError(symbol)

    async def get_assets(
        self,
        search: str | None = None,
        category: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> AssetsListResponse:
        """GET /api/public/v1/assets"""
        params: dict[str, Any] = {"page": page, "limit": limit}
        if search:
            params["search"] = search
        if category:
            params["category"] = category
        resp = await self._request("GET", "/api/public/v1/assets", params=params)
        return self._parse_model(AssetsListResponse, resp)

    async def get_exchange_rate(self, source_currency: str, dest_currency: str) -> ExchangeRateData:
        """GET /api/public/v1/rates?source_currency=...&dest_currency=..."""
        s = source_currency.upper()
        d = dest_currency.upper()
        if s == d:
            return ExchangeRateData(
                source_currency=s,
                dest_currency=d,
                pair=f"{s}{d}",
                rate=1.0,
                updated_at=None,
            )
        try:
            resp = await self._request(
                "GET",
                "/api/public/v1/rates",
                params={"source_currency": s, "dest_currency": d},
            )
            parsed = self._parse_model(ExchangeRateResponse, resp)
            return parsed.data
        except WallbitNotFoundError:
            raise ExchangeRateUnavailableError(f"{s}/{d}")

    async def create_trade(self, request: TradeRequest) -> TradeResult:
        """POST /api/public/v1/trades"""
        if settings.MULTI_USER_ENABLED:
            raise OrderExecutionError("Las compras reales aún no están habilitadas en modo multiusuario.")
        try:
            resp = await self._request(
                "POST",
                "/api/public/v1/trades",
                json_data=request.model_dump(exclude_none=True),
                max_retries=0,  # Never retry trades automatically
            )
            parsed = self._parse_model(TradeResponse, resp)
            return parsed.data
        except WallbitApiException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing trade: {e}")
            raise OrderExecutionError(details=str(e))

    async def get_transactions(
        self,
        page: int = 1,
        limit: int = 10,
        status: str | None = None,
        tx_type: str | None = None,
        currency: str | None = None,
    ) -> TransactionsData:
        """GET /api/public/v1/transactions"""
        params: dict[str, Any] = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        if tx_type:
            params["type"] = tx_type
        if currency:
            params["currency"] = currency
        resp = await self._request("GET", "/api/public/v1/transactions", params=params)
        parsed = self._parse_model(TransactionsResponse, resp)
        return parsed.data
