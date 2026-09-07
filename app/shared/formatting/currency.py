"""Monetary and quantity formatting utilities."""


def format_usd(amount: float | None) -> str:
    """Format an amount in USD: e.g. $1,245.32"""
    if amount is None:
        return "$0.00 USD"
    return f"${amount:,.2f} USD"


def format_currency(amount: float | None, currency: str) -> str:
    """
    Format an amount in the specified currency.
    For CLP and ARS, amounts are typically formatted without decimals or with dot separators.
    For USD/EUR/USDC, standard 2-decimal format.
    """
    if amount is None:
        return f"$0 {currency.upper()}"

    curr = currency.upper()
    if curr in ["CLP", "ARS"]:
        formatted = f"{int(round(amount)):,}".replace(",", ".")
        return f"${formatted} {curr}"
    elif curr == "EUR":
        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"€{formatted} EUR"
    else:
        return f"${amount:,.2f} {curr}"


def format_quantity(qty: float | None) -> str:
    """Format asset shares/quantity cleanly without trailing zeros if integer."""
    if qty is None:
        return "0"
    if qty.is_integer():
        return str(int(qty))
    formatted = f"{qty:.6f}".rstrip("0").rstrip(".")
    return formatted
