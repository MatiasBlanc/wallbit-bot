"""/saldo command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.constants import SUPPORTED_CURRENCIES
from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.infrastructure.wallbit.exceptions import WallbitApiException
from app.modules.balance.service import BalanceService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.formatting.currency import format_currency, format_usd
from app.shared.presentation.messages import edit_or_reply, format_error, format_loading

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
                    f"No reconozco la moneda <b>{arg}</b>. Prueba: {supported_str}"
                )
                return
            target_currency = arg

        loading = await update.effective_message.reply_text(format_loading("Consultando Wallbit"))
        try:
            balance_info = await balance_service.get_balance(target_currency=target_currency)
        except WallbitApiException as error:
            await edit_or_reply(loading, f"⚠️ {format_error(error)}")
            return
        except Exception as error:
            logger.exception("Error executing /saldo")
            await edit_or_reply(loading, format_error(error))
            return

        lines = ["💰 <b>Saldo</b>\n"]
        cash = balance_info.investment_cash_usd or 0
        has_split = cash > 0 and balance_info.checking_usd is not None
        has_investments = (
            balance_info.total_wealth_usd is not None
            and abs(balance_info.total_wealth_usd - balance_info.available_usd) > 0.005
        )

        # Sin cash ni portafolio, Checking = Disponible = Patrimonio: un solo importe basta.
        if has_split:
            lines.append(f"<b>Cuenta</b>\n{format_usd(balance_info.checking_usd)}\n")
            lines.append(f"<b>Efectivo en inversiones</b>\n{format_usd(cash)}\n")
            lines.append(f"<b>Disponible</b>\n{format_usd(balance_info.available_usd)}\n")
        else:
            lines.append(f"{format_usd(balance_info.available_usd)}\n")

        if has_investments:
            lines.append(f"<b>Patrimonio</b>\n{format_usd(balance_info.total_wealth_usd)}\n")

        if target_currency != "USD" and balance_info.converted_available is not None:
            total_conv = (
                balance_info.converted_total_wealth if has_investments else balance_info.converted_available
            )
            if total_conv is not None:
                lines.append(f"≈ {format_currency(total_conv, target_currency)}")

        message_text = "\n".join(lines).strip()
        await edit_or_reply(loading, message_text, parse_mode="HTML")

    return balance_command
