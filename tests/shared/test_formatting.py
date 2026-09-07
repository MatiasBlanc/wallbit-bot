"""Tests for formatting utilities."""

from app.shared.formatting.currency import format_currency, format_quantity, format_usd
from app.shared.formatting.percentage import format_percentage, get_performance_icon


def test_format_usd():
    assert format_usd(1245.32) == "$1,245.32 USD"
    assert format_usd(0.0) == "$0.00 USD"
    assert format_usd(None) == "$0.00 USD"
    assert format_usd(50) == "$50.00 USD"


def test_format_currency():
    # CLP with dots
    assert format_currency(1070000, "CLP") == "$1.070.000 CLP"
    assert format_currency(950.4, "CLP") == "$950 CLP"
    # ARS
    assert format_currency(120000, "ARS") == "$120.000 ARS"
    # EUR
    assert "EUR" in format_currency(1234.56, "EUR")
    # USD
    assert format_currency(100.5, "USD") == "$100.50 USD"


def test_format_percentage():
    assert format_percentage(5.42) == "+5.42%"
    assert format_percentage(-2.14) == "-2.14%"
    assert format_percentage(0.0) == "0.00%"
    assert format_percentage(None) == "N/D"


def test_format_quantity():
    assert format_quantity(10.0) == "10"
    assert format_quantity(0.8504) == "0.8504"
    assert format_quantity(1.500000) == "1.5"
    assert format_quantity(None) == "0"


def test_get_performance_icon():
    assert get_performance_icon(5.0) == "🟢"
    assert get_performance_icon(-3.2) == "🔴"
    assert get_performance_icon(0.0) == "⚪"
    assert get_performance_icon(None) == "⚪"
