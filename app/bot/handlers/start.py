"""/start command handler."""

from telegram import Update
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import restricted
from app.db.database import get_db_session
from app.db.repositories.user_settings_repo import UserSettingsRepository
from app.wallbit.client import WallbitClient

logger = get_logger(__name__)


def get_start_handler(client: WallbitClient, user_repo: UserSettingsRepository):
    @restricted
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        with get_db_session() as session:
            user_repo.get_or_create(session, user_id)
            session.commit()

        # Check Wallbit connection
        wallbit_ok = await client.check_connection()
        conn_status = "🟢 Conectado" if wallbit_ok else "🔴 Desconectado (verifica WALLBIT_API_KEY)"

        text = (
            "🤖 <b>Wallbit Assistant</b>\n\n"
            "Tu asistente personal para controlar saldo e inversiones.\n\n"
            f"<b>Estado Wallbit:</b> {conn_status}\n"
            f"<b>Modo operaciones:</b> {'🟢 Operación Real' if settings.TRADING_ENABLED else '🧪 Simulación (Dry-run)'}\n\n"
            "<b>Comandos disponibles:</b>\n"
            "Saldo: /saldo\n"
            "Inversiones: /inv\n"
            "DCA: /dca\n"
            "Alertas: /alerta\n"
            "Historial: /historial\n"
            "Reporte: /reporte\n"
            "Configuración: /config"
        )
        if update.effective_message:
            await update.effective_message.reply_text(text, parse_mode="HTML")

    return start_command
