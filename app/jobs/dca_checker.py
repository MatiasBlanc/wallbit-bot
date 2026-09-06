"""DCA due rules checker job."""

from datetime import datetime, timezone

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.logging import get_logger
from app.db.database import get_db_session
from app.db.models import DCARule, UserSettings
from app.services.dca_service import DCAService

logger = get_logger(__name__)


async def run_dca_checker(bot: Bot, dca_service: DCAService) -> None:
    """Check due DCA rules and dispatch notifications with confirmation buttons."""
    with get_db_session() as session:
        now_utc = datetime.now(timezone.utc)
        due_rules = (
            session.query(DCARule)
            .filter(DCARule.enabled.is_(True), DCARule.next_execution_at <= now_utc)
            .all()
        )

        for rule in due_rules:
            user = session.query(UserSettings).filter(UserSettings.id == rule.user_id).first()
            if not user:
                continue

            try:
                has_funds, pending_order, available_usd, current_price = await dca_service.trigger_dca_rule(
                    session=session, rule=rule, user=user
                )
                session.commit()

                if has_funds and pending_order:
                    price_line = f"Precio actual: ${current_price:,.2f}\n" if current_price else ""
                    msg = (
                        f"📈 <b>Compra programada</b>\n\n"
                        f"Hoy corresponde tu DCA:\n\n"
                        f"<b>{rule.ticker}</b>\n"
                        f"Monto: ${rule.amount_usd:,.2f} USD\n"
                        f"{price_line}\n"
                        f"Saldo disponible:\n"
                        f"${available_usd:,.2f}\n\n"
                        f"¿Quieres ejecutar la compra?"
                    )
                    keyboard = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Confirmar compra",
                                    callback_data=f"order_confirm:{pending_order.id}",
                                ),
                                InlineKeyboardButton(
                                    "Omitir",
                                    callback_data=f"order_skip:{pending_order.id}",
                                ),
                            ]
                        ]
                    )
                    await bot.send_message(
                        chat_id=user.telegram_user_id,
                        text=msg,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                else:
                    # Insufficient funds
                    msg = (
                        f"⚠️ <b>DCA no ejecutado</b>\n\n"
                        f"{rule.ticker} — ${rule.amount_usd:,.2f} USD\n\n"
                        f"Saldo disponible:\n"
                        f"${available_usd:,.2f}\n\n"
                        f"No tienes saldo suficiente."
                    )
                    await bot.send_message(
                        chat_id=user.telegram_user_id,
                        text=msg,
                        parse_mode="HTML",
                    )

            except Exception as e:
                logger.error(f"Error executing DCA check for rule_id={rule.id}: {e}")
