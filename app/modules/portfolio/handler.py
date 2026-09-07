"""/inv command handler for portfolio and position detail."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.infrastructure.wallbit.exceptions import (
    InvalidTickerError,
    PositionNotFoundError,
    WallbitApiException,
)
from app.modules.portfolio.service import PortfolioService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.formatting.currency import format_quantity, format_usd
from app.shared.formatting.percentage import format_percentage, get_performance_icon
from app.shared.presentation.messages import edit_or_reply, format_error, format_loading

logger = get_logger(__name__)


def get_investments_handler(portfolio_service: PortfolioService, user_repo: UserSettingsRepository):
    @restricted
    async def investments_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            user_db_id = user.id

            # Check if specific ticker requested, e.g. /inv VOO
            loading = await update.effective_message.reply_text(format_loading("Consultando inversiones"))
            if context.args:
                ticker = context.args[0].upper().strip()
                try:
                    pos = await portfolio_service.get_position(
                        ticker=ticker, session=session, user_id=user_db_id
                    )
                except PositionNotFoundError:
                    await edit_or_reply(loading, f"No tienes {ticker} en tu cuenta.")
                    return
                except InvalidTickerError:
                    await edit_or_reply(loading, f"No encontré {ticker} en Wallbit.")
                    return
                except WallbitApiException as error:
                    await edit_or_reply(loading, f"⚠️ {format_error(error)}")
                    return
                except Exception as error:
                    logger.exception(f"Error fetching position for {ticker}")
                    await edit_or_reply(loading, format_error(error))
                    return

                # Build detail message
                lines = [f"📈 <b>{pos.ticker}</b> - {pos.name}\n"]
                lines.append(f"<b>Cantidad</b>\n{format_quantity(pos.shares)}\n")

                if pos.avg_price is not None:
                    lines.append(f"<b>Precio promedio</b>\n{format_usd(pos.avg_price)}\n")

                lines.append(f"<b>Precio actual</b>\n{format_usd(pos.current_price)}\n")

                if pos.cost_basis is not None:
                    lines.append(f"<b>Invertido</b>\n{format_usd(pos.cost_basis)}\n")

                lines.append(f"<b>Valor actual</b>\n{format_usd(pos.current_value)}\n")

                if pos.gain_abs is not None:
                    sign = "+" if pos.gain_abs > 0 else ""
                    lines.append(f"<b>Ganancia</b>\n{sign}${pos.gain_abs:,.2f}\n")

                if pos.roi_pct is not None:
                    lines.append(f"<b>Rentabilidad</b>\n{format_percentage(pos.roi_pct)}")

                msg_text = "\n".join(lines).strip()
                await edit_or_reply(loading, msg_text, parse_mode="HTML")
                return

            # Entire portfolio overview (/inv)
            try:
                summary = await portfolio_service.get_portfolio(session=session, user_id=user_db_id)
            except WallbitApiException as error:
                await edit_or_reply(loading, f"⚠️ {format_error(error)}")
                return
            except Exception as error:
                logger.exception("Error fetching portfolio")
                await edit_or_reply(loading, format_error(error))
                return

            if not summary.positions:
                await edit_or_reply(loading, "Aún no tienes inversiones en Wallbit.")
                return

            lines = ["<b>Inversiones</b>\n"]
            for p in summary.positions:
                lines.append(f"<b>{p.ticker}</b>")
                lines.append(format_usd(p.current_value) if p.current_value is not None else "Cotización no disponible")
                if p.gain_abs is not None and p.roi_pct is not None:
                    icon = get_performance_icon(p.roi_pct)
                    sign = "+" if p.gain_abs > 0 else ""
                    lines.append(f"{icon} {sign}${p.gain_abs:,.2f} ({format_percentage(p.roi_pct)})\n")
                else:
                    lines.append("⚪ Rentabilidad no disponible\n")

            lines.append("────────────\n")
            if summary.total_invested is not None:
                lines.append(f"Invertido: {format_usd(summary.total_invested)}")
            value_text = format_usd(summary.total_current_value) if summary.total_current_value is not None else "N/D"
            lines.append(f"Valor actual: {value_text}")
            if summary.total_gain_abs is not None:
                sign = "+" if summary.total_gain_abs > 0 else ""
                lines.append(f"Ganancia: {sign}${summary.total_gain_abs:,.2f}")
            if summary.total_roi_pct is not None:
                lines.append(f"Rentabilidad: {format_percentage(summary.total_roi_pct)}")

            msg_text = "\n".join(lines).strip()
            await edit_or_reply(loading, msg_text, parse_mode="HTML")

    return investments_command
