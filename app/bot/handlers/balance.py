"""/saldo command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.constants import SUPPORTED_CURRENCIES
from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.services.balance_service import BalanceService
from app.utils.formatting import format_currency, format_usd
from app.wallbit.exceptions import WallbitApiException

logger = get_logger(__name__)


def get_balance_handler(balance_service: BalanceService, user_repo: UserSettingsRepository):
    @restricted
    async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            default_currency = user.default_currency

        # Parse target currency from args if passed, e.g. /saldo EUR
        target_currency = default_currency
        if context.args:
            arg = context.args[0].upper().strip()
            if arg not in SUPPORTED_CURRENCIES:
                supported_str = ", ".join(SUPPORTED_CURRENCIES)
                await update.effective_message.reply_text(
                    f"⚠️ Moneda no soportada '{arg}'.\nMonedas disponibles: {supported_str}"
                )
                return
            target_currency = arg

        try:
            balance_info = await balance_service.get_balance(target_currency=target_currency)
        except WallbitApiException as e:
            await update.effective_message.reply_text(f"⚠️ {e.user_message}")
            return
        except Exception:
            logger.exception("Error executing /saldo")
            await update.effective_message.reply_text(
                "Wallbit no está disponible temporalmente. Inténtalo nuevamente más tarde."
            )
            return

        lines = ["💰 <b>Saldo</b>\n"]

        if balance_info.checking_usd is not None:
            lines.append(f"<b>Checking</b>\n{format_usd(balance_info.checking_usd)}\n")

        if balance_info.investment_cash_usd is not None:
            lines.append(f"<b>Cash de inversión</b>\n{format_usd(balance_info.investment_cash_usd)}\n")

        lines.append(f"<b>Disponible</b>\n{format_usd(balance_info.available_usd)}\n")

        if balance_info.total_wealth_usd is not None:
            lines.append(f"<b>Patrimonio total</b>\n{format_usd(balance_info.total_wealth_usd)}\n")

        # Converted line if different from USD
        if target_currency != "USD" and balance_info.converted_available is not None:
            total_conv = balance_info.converted_total_wealth or balance_info.converted_available
            lines.append(f"≈ {format_currency(total_conv, target_currency)}")

        message_text = "\n".join(lines).strip()
        await update.effective_message.reply_text(message_text, parse_mode="HTML")

    return balance_command
