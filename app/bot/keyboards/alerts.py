"""Inline keyboards for price and FX alerts."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_alerts_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Crear alerta", callback_data="alert_menu:create")],
            [InlineKeyboardButton("🔔 Mis alertas", callback_data="alert_menu:list")],
            [InlineKeyboardButton("❌ Cerrar", callback_data="alert_menu:close")],
        ]
    )


def get_alert_item_keyboard(alert_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑 Eliminar", callback_data=f"alert_delete:{alert_id}")]
        ]
    )
