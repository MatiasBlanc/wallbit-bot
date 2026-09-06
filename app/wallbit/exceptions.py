"""Wallbit API and domain exceptions."""



class WallbitApiException(Exception):
    """Base exception for Wallbit API errors."""

    def __init__(self, user_message: str, status_code: int | None = None, details: str | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code
        self.details = details

    def __str__(self) -> str:
        code_str = f" [{self.status_code}]" if self.status_code else ""
        return f"{self.user_message}{code_str}"


class WallbitAuthenticationError(WallbitApiException):
    """401 Unauthorized - Invalid or missing API key."""

    def __init__(self, message: str = "Error de autenticación con Wallbit. Verifica tu API Key.", details: str | None = None):
        super().__init__(user_message=message, status_code=401, details=details)


class WallbitForbiddenError(WallbitApiException):
    """403 Forbidden - Insufficient permissions."""

    def __init__(self, message: str = "Permisos insuficientes en tu API Key de Wallbit.", details: str | None = None):
        super().__init__(user_message=message, status_code=403, details=details)


class WallbitNotFoundError(WallbitApiException):
    """404 Not Found."""

    def __init__(self, message: str = "Recurso no encontrado en Wallbit.", details: str | None = None):
        super().__init__(user_message=message, status_code=404, details=details)


class WallbitRateLimitError(WallbitApiException):
    """429 Too Many Requests."""

    def __init__(self, retry_after: int = 5, message: str = "Límite de solicitudes alcanzado en Wallbit. Intenta más tarde."):
        super().__init__(user_message=message, status_code=429)
        self.retry_after = retry_after


class WallbitUnavailableError(WallbitApiException):
    """5xx Server Error or Connection Failure."""

    def __init__(self, message: str = "Wallbit no está disponible temporalmente. Inténtalo nuevamente más tarde.", status_code: int | None = 503, details: str | None = None):
        super().__init__(user_message=message, status_code=status_code, details=details)


class WallbitKYCRequiredError(WallbitApiException):
    """412 Account requires KYC or migration."""

    def __init__(self, message: str = "Tu cuenta requiere verificación KYC o configuración adicional antes de operar.", details: str | None = None):
        super().__init__(user_message=message, status_code=412, details=details)


class WallbitValidationError(WallbitApiException):
    """422 Validation error."""

    def __init__(self, message: str = "Datos inválidos enviados a Wallbit.", details: str | None = None):
        super().__init__(user_message=message, status_code=422, details=details)


class InsufficientFundsError(WallbitApiException):
    """Insufficient funds to execute order or transfer."""

    def __init__(self, message: str = "No tienes saldo suficiente para realizar esta operación.", details: str | None = None):
        super().__init__(user_message=message, status_code=400, details=details)


class PositionNotFoundError(WallbitApiException):
    """User has no position for specified ticker."""

    def __init__(self, ticker: str):
        super().__init__(user_message=f"No tienes una posición abierta en {ticker.upper()}.", status_code=404)
        self.ticker = ticker.upper()


class InvalidTickerError(WallbitApiException):
    """Ticker symbol is not valid or not found."""

    def __init__(self, ticker: str):
        super().__init__(user_message=f"No pude encontrar el activo '{ticker.upper()}'. Verifica el símbolo.", status_code=404)
        self.ticker = ticker.upper()


class OrderExecutionError(WallbitApiException):
    """Error during order execution."""

    def __init__(self, message: str = "No pudimos ejecutar la compra.", status_code: int | None = None, details: str | None = None):
        super().__init__(user_message=message, status_code=status_code, details=details)


class ExchangeRateUnavailableError(WallbitApiException):
    """Exchange rate could not be retrieved."""

    def __init__(self, pair: str):
        super().__init__(user_message=f"Tipo de cambio no disponible para {pair}.", status_code=404)
        self.pair = pair
