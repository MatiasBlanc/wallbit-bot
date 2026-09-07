"""Application constants."""

SUPPORTED_CURRENCIES = ["CLP", "USD", "ARS", "EUR", "USDC"]
CURRENCY_FLAGS = {
    "CLP": "🇨🇱",
    "USD": "🇺🇸",
    "ARS": "🇦🇷",
    "EUR": "🇪🇺",
    "USDC": "💵",
}

# Order statuses
ORDER_STATUS_PENDING = "pending"
ORDER_STATUS_CONFIRMED = "confirmed"
ORDER_STATUS_EXPIRED = "expired"
ORDER_STATUS_EXECUTED = "executed"
ORDER_STATUS_FAILED = "failed"
# La respuesta de una orden puede quedar indeterminada tras un timeout o 5xx.
ORDER_STATUS_UNKNOWN = "verification_required"

# DCA Frequencies
DCA_FREQ_WEEKLY = "weekly"
DCA_FREQ_MONTHLY = "monthly"

WEEKDAY_NAMES_ES = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}

# Alert types
ALERT_TYPE_PRICE = "price"
ALERT_TYPE_FX = "exchange_rate"

# Operators
OPERATOR_GTE = ">="
OPERATOR_LTE = "<="

# Transaction sources and types
TX_TYPE_BUY = "BUY"
TX_TYPE_SELL = "SELL"
TX_TYPE_DEPOSIT = "DEPOSIT"
TX_TYPE_DCA_BUY = "DCA_BUY"

TX_SOURCE_DCA = "DCA"
TX_SOURCE_MANUAL = "MANUAL"
