"""Monetary and percentage formatting utilities."""



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
        # Round to integer for CLP/ARS presentation or standard dot separator
        formatted = f"{int(round(amount)):,}".replace(",", ".")
        return f"${formatted} {curr}"
    elif curr == "EUR":
        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"€{formatted} EUR"
    else:
        return f"${amount:,.2f} {curr}"


def format_percentage(pct: float | None) -> str:
    """Format percentage with +/- sign: e.g. +5.42%, -2.14%"""
    if pct is None:
        return "N/D"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


def format_quantity(qty: float | None) -> str:
    """Format asset shares/quantity cleanly without trailing zeros if integer."""
    if qty is None:
        return "0"
    if qty.is_integer():
        return str(int(qty))
    # Otherwise format with up to 6 decimal places, stripping trailing zeros
    formatted = f"{qty:.6f}".rstrip("0").rstrip(".")
    return formatted


def get_performance_icon(value: float | None) -> str:
    """
    Return performance icon:
    🟢 positive (> 0)
    🔴 negative (< 0)
    ⚪ zero or undefined
    """
    if value is None or abs(value) < 1e-6:
        return "⚪"
    return "🟢" if value > 0 else "🔴"
