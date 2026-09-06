"""Inline keyboards for DCA management."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_dca_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Crear DCA", callback_data="dca_menu:create")],
            [InlineKeyboardButton("📈 Ver DCA activos", callback_data="dca_menu:active")],
            [InlineKeyboardButton("⏸ Ver pausados", callback_data="dca_menu:paused")],
            [InlineKeyboardButton("❌ Cerrar", callback_data="dca_menu:close")],
        ]
    )


def get_dca_item_keyboard(rule_id: int, is_active: bool) -> InlineKeyboardMarkup:
    if is_active:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("⏸ Pausar", callback_data=f"dca_pause:{rule_id}"),
                    InlineKeyboardButton("🗑 Eliminar", callback_data=f"dca_delete:{rule_id}"),
                ]
            ]
        )
    else:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("▶️ Reactivar", callback_data=f"dca_resume:{rule_id}"),
                    InlineKeyboardButton("🗑 Eliminar", callback_data=f"dca_delete:{rule_id}"),
                ]
            ]
        )
