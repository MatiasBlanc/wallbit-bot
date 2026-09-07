"""Comandos públicos de vinculación; nunca solicitan claves Wallbit por Telegram."""

from telegram import Update
from telegram.constants import ChatType
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app.core.config import settings
from app.core.logging import get_logger
from app.infrastructure.database.database import get_db_session
from app.modules.auth.service import logout, redeem_login_code

logger = get_logger(__name__)


async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Vincula la identidad Telegram mediante un código temporal del administrador.

    Args:
        update: Actualización de Telegram; se exige chat privado y usuario real.
        context: Contexto con los argumentos del comando, no se guarda en user_data.

    Returns:
        None. Informa éxito o un error genérico sin revelar credenciales.

    Raises:
        TelegramError: Si no puede enviarse la respuesta.
        sqlalchemy.exc.SQLAlchemyError: Si falla el canje atómico.
    """
    if not update.effective_user or not update.effective_message or not update.effective_chat:
        return
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text("Abre un chat privado con el bot. No envíes códigos ni claves en grupos.")
        return
    if not settings.MULTI_USER_ENABLED:
        await update.effective_message.reply_text("Este bot está configurado en modo privado, sin login multiusuario.")
        return
    if len(context.args or []) != 1:
        await update.effective_message.reply_text(
            f"Tu ID de Telegram es {update.effective_user.id}.\n"
            "Solicita al administrador un código para este ID y usa /login CODIGO.\n"
            "No envíes tu API key de Wallbit por Telegram."
        )
        return
    code = context.args[0]
    context.args.clear()
    try:
        await update.effective_message.delete()
    except TelegramError:
        logger.warning("No se pudo borrar un mensaje de vinculación; no se registró su contenido.")
    with get_db_session() as session:
        is_valid = redeem_login_code(session, update.effective_user.id, code)
    del code
    await update.effective_message.reply_text(
        "Cuenta vinculada. Usa /start, /saldo o /config."
        if is_valid else "Código inválido, vencido o ya utilizado. Solicita uno nuevo al administrador."
    )


async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Desconecta únicamente al usuario Telegram que invoca el comando.

    Args:
        update: Actualización de un chat privado.
        context: Contexto Telegram, cuyos datos de conversación se limpian.

    Returns:
        None. No revoca la API key en Wallbit ni elimina el historial.

    Raises:
        TelegramError: Si no puede enviarse la respuesta.
        sqlalchemy.exc.SQLAlchemyError: Si falla la desactivación.
    """
    if not update.effective_user or not update.effective_message or not update.effective_chat:
        return
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.effective_message.reply_text("Usa este comando en un chat privado con el bot.")
        return
    if not settings.MULTI_USER_ENABLED:
        await update.effective_message.reply_text("El login multiusuario no está habilitado.")
        return
    with get_db_session() as session:
        logout(session, update.effective_user.id)
    context.user_data.clear()
    await update.effective_message.reply_text(
        "Cuenta desconectada. DCA y alertas quedan pausados; las órdenes pendientes expiraron.\n"
        "Conservamos tu historial y credencial cifrada. Para volver, solicita otro código.\n"
        "Para revocar también la API key, hazlo desde Wallbit."
    )
