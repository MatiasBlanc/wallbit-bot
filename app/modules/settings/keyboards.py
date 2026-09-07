"""Inline keyboards for configuration menu."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.core.constants import CURRENCY_FLAGS, SUPPORTED_CURRENCIES

TIMEZONE_LABELS = {
    "America/Santiago": "Santiago",
    "America/Argentina/Buenos_Aires": "Buenos Aires",
    "America/Bogota": "Bogotá",
    "America/Mexico_City": "Ciudad de México",
    "Europe/Madrid": "Madrid",
    "UTC": "UTC",
}


def timezone_label(timezone_name: str) -> str:
    """Nombre corto de zona horaria para mostrar en Telegram."""
    return TIMEZONE_LABELS.get(timezone_name, timezone_name)


MAIN_MENU_LABELS = {
    "💰 Saldo": "saldo",
    "📊 Inversiones": "inv",
    "🔁 Compras": "dca",
    "🔔 Alertas": "alerta",
    "🧾 Movimientos": "historial",
    "☀️ Resumen": "reporte",
    "🤖 Analizar": "analizar",
    "⚙️ Ajustes": "config",
}

REPORT_TIME_PRESETS = ("08:00", "09:00", "12:00", "18:00", "21:00")

CURRENCY_NAMES = {
    "CLP": "Peso chileno",
    "USD": "Dólar",
    "ARS": "Peso argentino",
    "EUR": "Euro",
    "USDC": "USDC",
}


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    """Atajos con nombres claros; no dependen de un callback."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💰 Saldo"), KeyboardButton("📊 Inversiones")],
            [KeyboardButton("🔁 Compras"), KeyboardButton("🔔 Alertas")],
            [KeyboardButton("🧾 Movimientos"), KeyboardButton("☀️ Resumen")],
            [KeyboardButton("🤖 Analizar"), KeyboardButton("⚙️ Ajustes")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Elige una opción o escribe un comando",
    )


def get_report_time_keyboard() -> InlineKeyboardMarkup:
    """Horas habituales; también se puede escribir HH:MM."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(hour, callback_data=f"report_time:{hour}") for hour in REPORT_TIME_PRESETS[:3]],
            [InlineKeyboardButton(hour, callback_data=f"report_time:{hour}") for hour in REPORT_TIME_PRESETS[3:]],
            [InlineKeyboardButton("Cancelar", callback_data="cancel_config_conv")],
        ]
    )


def get_config_main_keyboard(alerts_enabled: bool) -> InlineKeyboardMarkup:
    alerts_text = "🔔 Activadas" if alerts_enabled else "🔕 Pausadas"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💱 Moneda", callback_data="config:currency"),
                InlineKeyboardButton("⏰ Hora", callback_data="config:report_time"),
            ],
            [
                InlineKeyboardButton("🌍 Zona", callback_data="config:timezone"),
                InlineKeyboardButton(alerts_text, callback_data="config:toggle_alerts"),
            ],
            [InlineKeyboardButton("Conexión Wallbit", callback_data="config:status")],
            [InlineKeyboardButton("Listo", callback_data="config:close")],
        ]
    )


def get_currency_keyboard(current_currency: str) -> InlineKeyboardMarkup:
    buttons = []
    for curr in SUPPORTED_CURRENCIES:
        flag = CURRENCY_FLAGS.get(curr, "")
        title = CURRENCY_NAMES.get(curr, curr)
        name = f"{flag} {curr} · {title}".strip()
        label = f"✓ {name}" if curr == current_currency else name
        buttons.append(InlineKeyboardButton(label, callback_data=f"set_currency:{curr}"))

    keyboard = [[button] for button in buttons]
    keyboard.append([InlineKeyboardButton("Volver", callback_data="config:back")])
    return InlineKeyboardMarkup(keyboard)


def get_timezone_keyboard(current_tz: str) -> InlineKeyboardMarkup:
    common_tzs = list(TIMEZONE_LABELS.items())
    buttons = []
    for tz_code, label in common_tzs:
        prefix = "✓ " if tz_code == current_tz else ""
        buttons.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=f"set_tz:{tz_code}")])
    buttons.append([InlineKeyboardButton("Volver", callback_data="config:back")])
    return InlineKeyboardMarkup(buttons)
