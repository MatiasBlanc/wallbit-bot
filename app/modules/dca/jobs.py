"""DCA due rules checker job."""

from datetime import datetime, timezone

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.database import get_db_session
from app.modules.auth.jobs import for_each_account, job_telegram_user_id
from app.modules.auth.models import WallbitCredential
from app.modules.dca.models import DCARule
from app.modules.dca.service import DCAService
from app.modules.orders.fees import estimate_trade_fee, format_fee_summary
from app.shared.concurrency import map_limited
from app.shared.datetime import ensure_utc

logger = get_logger(__name__)


@for_each_account
async def run_dca_checker(bot: Bot, dca_service: DCAService) -> None:
    """Check due DCA rules and dispatch notifications with confirmation buttons."""
    with get_db_session() as session:
        now_utc = datetime.now(timezone.utc)
        due_rules = dca_service.dca_repo.get_due_rules(session, now_utc, telegram_user_id=job_telegram_user_id())

        if not due_rules:
            return
        # Una lectura de fondos por cuenta/ciclo; confirmar una compra siempre vuelve a consultarlos.
        accounts = await dca_service.balance_service.get_account_balances()
        symbols = list(dict.fromkeys(rule.ticker for rule in due_rules))
        quotes = await map_limited(symbols, dca_service.client.get_asset, settings.WALLBIT_MAX_CONCURRENT_REQUESTS)
        prices = {}
        for symbol, quote in zip(symbols, quotes, strict=True):
            if isinstance(quote, Exception):
                logger.warning("No se pudo cotizar %s durante el ciclo DCA: %s", symbol, quote)
                prices[symbol] = None
            else:
                prices[symbol] = quote.price

        for rule in due_rules:
            user = rule.user
            if not user:
                continue

            rule_id = rule.id
            try:
                # Durante las lecturas HTTP el usuario pudo pausar, eliminar o desconectar su cuenta.
                rule = session.query(DCARule).populate_existing().filter(DCARule.id == rule_id).first()
                if rule is None or not rule.enabled or ensure_utc(rule.next_execution_at) > now_utc:
                    continue
                if settings.MULTI_USER_ENABLED:
                    credential = session.get(WallbitCredential, user.telegram_user_id, populate_existing=True)
                    if credential is None or not credential.is_active:
                        continue
                fee_estimate = estimate_trade_fee(session, user, rule.amount_usd)
                has_funds, pending_order, available_usd, current_price = await dca_service.trigger_dca_rule(
                    session=session, rule=rule, user=user, account_balances=accounts, market_prices=prices
                )
                session.commit()

                if has_funds and pending_order:
                    price_line = f"Precio actual: ${current_price:,.2f}\n" if current_price else ""
                    asset_label = rule.asset_name and (
                        f"{rule.ticker} ({rule.asset_name})"
                        if rule.asset_name.strip().upper() != rule.ticker.upper() else rule.ticker
                    ) or rule.ticker
                    msg = (
                        "<b>Hoy toca comprar</b>\n\n"
                        f"<b>{asset_label}</b>\n"
                        f"{format_fee_summary(fee_estimate)}\n"
                        f"{price_line}\n"
                        f"Saldo disponible: ${available_usd:,.2f} USD\n\n"
                        "<i>La comisión final la determina Wallbit según tu plan.</i>"
                    )
                    keyboard = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "Comprar",
                                    callback_data=f"order_confirm:{pending_order.id}",
                                ),
                                InlineKeyboardButton(
                                    "Ahora no",
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
                    asset_label = rule.asset_name and (
                        f"{rule.ticker} ({rule.asset_name})"
                        if rule.asset_name.strip().upper() != rule.ticker.upper() else rule.ticker
                    ) or rule.ticker
                    msg = (
                        "<b>No pude armar la compra</b>\n\n"
                        f"<b>{asset_label}</b>\n"
                        f"{format_fee_summary(fee_estimate, bold=False)}\n\n"
                        f"Saldo disponible: ${available_usd:,.2f} USD\n\n"
                        "No tienes saldo suficiente para cubrir el total aproximado."
                    )
                    await bot.send_message(
                        chat_id=user.telegram_user_id,
                        text=msg,
                        parse_mode="HTML",
                    )

            except Exception:
                session.rollback()
                logger.exception("Error al comprobar la regla DCA %s", rule_id)
