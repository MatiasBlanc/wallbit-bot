"""Percentage and performance icon formatting utilities."""


def format_percentage(pct: float | None) -> str:
    """Format percentage with +/- sign: e.g. +5.42%, -2.14%"""
    if pct is None:
        return "N/D"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


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
