"""Interfaz Telegram del advisor opcional."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from app.core.logging import get_logger
from app.core.security import restricted
from app.infrastructure.database.database import get_db_session
from app.modules.advisor.service import AdvisorDisabledError, AdvisorService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.presentation.messages import edit_or_reply, format_error, format_loading

logger = get_logger(__name__)


ANALYSIS_PROMPTS = {
    "summary": "Resume mi cartera de forma simple.",
    "risk": "¿Qué riesgos ves en mi distribución?",
    "concentration": "¿En qué estoy más concentrado?",
    "performance": "Explícame mi rendimiento.",
}


def get_advisor_keyboard() -> InlineKeyboardMarkup:
    """Opciones de análisis sin acciones financieras."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Resumen", callback_data="advisor:summary"),
                InlineKeyboardButton("⚠️ Riesgo", callback_data="advisor:risk"),
            ],
            [InlineKeyboardButton("🎯 Concentración", callback_data="advisor:concentration")],
            [InlineKeyboardButton("📈 Rendimiento", callback_data="advisor:performance")],
            [InlineKeyboardButton("✅ Cerrar", callback_data="advisor:close")],
        ]
    )


def get_advisor_handler(advisor_service: AdvisorService, user_repo: UserSettingsRepository):
    @restricted
    async def advisor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.args:
            await _run_analysis(
                update,
                advisor_service,
                user_repo,
                " ".join(context.args),
            )
            return
        await update.effective_message.reply_text(
            "🤖 <b>Análisis IA</b>\n\nElige una consulta de solo lectura o usa /analizar seguido de tu pregunta.",
            reply_markup=get_advisor_keyboard(),
            parse_mode="HTML",
        )

    return advisor_command


async def _run_analysis(
    update: Update,
    advisor_service: AdvisorService,
    user_repo: UserSettingsRepository,
    prompt: str,
) -> None:
    user_id = update.effective_user.id
    query = update.callback_query
    if query is not None:
        await query.answer()
        if not isinstance(query.message, Message):
            raise ValueError("El callback no contiene un mensaje accesible.")
        loading = await query.message.reply_text(format_loading("Analizando tu cartera"))
    else:
        message = update.effective_message
        if message is None:
            raise ValueError("El comando no contiene un mensaje accesible.")
        loading = await message.reply_text(format_loading("Analizando tu cartera"))
    try:
        with get_db_session() as session:
            user = user_repo.get_or_create(session, user_id)
            result = await advisor_service.analyze(session, user, prompt)
    except AdvisorDisabledError as error:
        await edit_or_reply(loading, f"🔒 {error}")
        return
    except Exception as error:
        logger.exception("Error generating advisor analysis")
        await edit_or_reply(loading, format_error(error))
        return
    await edit_or_reply(loading, result, parse_mode="HTML")


def get_advisor_callbacks(advisor_service: AdvisorService, user_repo: UserSettingsRepository):
    @restricted
    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        action = query.data.split(":", 1)[1]
        if action == "close":
            await query.answer()
            await query.edit_message_text("Listo.")
            return
        prompt = ANALYSIS_PROMPTS.get(action)
        if prompt is None:
            await query.answer("Opción no válida.", show_alert=True)
            return
        await _run_analysis(update, advisor_service, user_repo, prompt)

    return handle_callback
