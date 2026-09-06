"""Inline keyboards for configuration menu."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.constants import SUPPORTED_CURRENCIES


def get_config_main_keyboard(alerts_enabled: bool) -> InlineKeyboardMarkup:
    alerts_text = "🔔 Alertas: Activadas" if alerts_enabled else "🔕 Alertas: Desactivadas"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💱 Moneda por defecto", callback_data="config:currency")],
            [InlineKeyboardButton("⏰ Hora del reporte", callback_data="config:report_time")],
            [InlineKeyboardButton("🌍 Zona horaria", callback_data="config:timezone")],
            [InlineKeyboardButton("🔌 Estado Wallbit", callback_data="config:status")],
            [InlineKeyboardButton(alerts_text, callback_data="config:toggle_alerts")],
            [InlineKeyboardButton("❌ Cerrar", callback_data="config:close")],
        ]
    )


def get_currency_keyboard(current_currency: str) -> InlineKeyboardMarkup:
    buttons = []
    for curr in SUPPORTED_CURRENCIES:
        label = f"✓ {curr}" if curr == current_currency else curr
        buttons.append(InlineKeyboardButton(label, callback_data=f"set_currency:{curr}"))

    # Arrange in rows of 2-3
    keyboard = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data="config:back")])
    return InlineKeyboardMarkup(keyboard)


def get_timezone_keyboard(current_tz: str) -> InlineKeyboardMarkup:
    common_tzs = [
        ("America/Santiago", "Santiago (Chile)"),
        ("America/Argentina/Buenos_Aires", "Buenos Aires"),
        ("America/Bogota", "Bogotá"),
        ("America/Mexico_City", "Ciudad de México"),
        ("Europe/Madrid", "Madrid"),
        ("UTC", "UTC"),
    ]
    buttons = []
    for tz_code, label in common_tzs:
        prefix = "✓ " if tz_code == current_tz else ""
        buttons.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=f"set_tz:{tz_code}")])
    buttons.append([InlineKeyboardButton("⬅️ Volver", callback_data="config:back")])
    return InlineKeyboardMarkup(buttons)
