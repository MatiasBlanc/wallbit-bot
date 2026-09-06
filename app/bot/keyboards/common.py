"""Common inline keyboards."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancelar", callback_data="cancel_flow")]]
    )


def get_back_keyboard(back_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Volver", callback_data=back_callback)]]
    )
