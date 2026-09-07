"""Cifrado de credenciales, canje atómico y revocación de sesiones."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.identity import AccountIdentity
from app.modules.alerts.models import Alert
from app.modules.auth.models import WallbitCredential
from app.modules.dca.models import DCARule
from app.modules.orders.models import PendingOrder
from app.modules.settings.models import UserSettings
from app.modules.settings.repository import UserSettingsRepository


def credential_cipher() -> Fernet:
    """Construye el cifrador usando exclusivamente el secreto del servidor.

    Returns:
        Cifrador autenticado Fernet.

    Raises:
        ValueError: Si falta la clave o no tiene el formato Fernet.
    """
    try:
        return Fernet(settings.CREDENTIAL_ENCRYPTION_KEY.get_secret_value().encode())
    except (ValueError, TypeError) as error:
        raise ValueError("Configura CREDENTIAL_ENCRYPTION_KEY con una clave Fernet válida.") from error


def validate_multi_user_config() -> None:
    """Verifica las condiciones de seguridad antes de iniciar bot o aprovisionamiento.

    Returns:
        None. El modo privado no necesita un secreto adicional.

    Raises:
        ValueError: Si falta cifrado, HTTPS o se intenta habilitar trading multiusuario.
    """
    if settings.MULTI_USER_ENABLED:
        raise ValueError("El modo multiusuario no forma parte del producto de instancia única.")
    url = urlsplit(settings.WALLBIT_BASE_URL)
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        raise ValueError("WALLBIT_BASE_URL debe ser HTTPS y no contener credenciales.")
    if settings.TRADING_ENABLED:
        raise ValueError("El modo multiusuario solo permite simulación hasta disponer de reconciliación de órdenes.")


def issue_login_code(
    session: Session, telegram_user_id: int, api_key: SecretStr | None = None, wallbit_plan: str | None = None,
) -> str:
    """Emite un código temporal ligado a un ID; no permite cambiar de cuenta implícitamente.

    Args:
        session: Sesión del administrador; el llamador confirma la transacción.
        telegram_user_id: ID positivo de Telegram obtenido en el chat privado.
        api_key: Clave validada para un alta nueva; None renueva una cuenta existente.
        wallbit_plan: Plan Classic, Pro o Max; obligatorio en altas y opcional en renovaciones.

    Returns:
        Código aleatorio de un solo uso; en la base solo se almacena su hash.

    Raises:
        ValueError: Si el ID, la clave o la operación de alta/renovación son inválidos.
        sqlalchemy.exc.SQLAlchemyError: Si falla la persistencia.
    """
    if telegram_user_id <= 0:
        raise ValueError("El ID de Telegram debe ser positivo.")
    plan = wallbit_plan.lower().strip() if wallbit_plan else None
    if plan is not None and plan not in {"classic", "pro", "max"}:
        raise ValueError("El plan debe ser classic, pro o max.")
    cipher = credential_cipher()
    credential = session.get(WallbitCredential, telegram_user_id)
    if credential is None:
        if api_key is None or not api_key.get_secret_value().strip():
            raise ValueError("Una cuenta nueva requiere su API key.")
        # Una cuenta privada previa podría contener órdenes de otro propietario.
        existing_user = UserSettingsRepository().get_by_telegram_id(session, telegram_user_id)
        if existing_user is not None:
            raise ValueError("Usa una base nueva para multiusuario: este ID ya contiene datos sin vinculación verificada.")
        credential = WallbitCredential(
            telegram_user_id=telegram_user_id,
            encrypted_api_key=cipher.encrypt(api_key.get_secret_value().encode()).decode(),
            wallbit_plan=plan or "classic",
            is_active=False,
        )
        session.add(credential)
    elif api_key is not None:
        raise ValueError("Esta cuenta ya existe. Usa --renew; cambiar de cuenta requiere una migración explícita.")
    elif plan is not None:
        credential.wallbit_plan = plan
    code = secrets.token_urlsafe(32)
    credential.login_code_hash = hashlib.sha256(code.encode()).hexdigest()
    credential.login_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.LOGIN_CODE_TTL_MINUTES)
    session.flush()
    return code


def redeem_login_code(session: Session, telegram_user_id: int, code: str) -> bool:
    """Canjea atómicamente un código vigente, exclusivamente para su destinatario.

    Args:
        session: Sesión del llamador; debe confirmar la transacción.
        telegram_user_id: Identidad suministrada por Telegram, nunca por el mensaje.
        code: Código temporal recibido por canal privado.

    Returns:
        True si se activó la cuenta; False si el código expiró, se usó o no corresponde.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Si falla la transacción.
    """
    if not 32 <= len(code) <= 128:
        return False
    result = session.execute(
        update(WallbitCredential)
        .where(
            WallbitCredential.telegram_user_id == telegram_user_id,
            WallbitCredential.login_code_hash == hashlib.sha256(code.encode()).hexdigest(),
            WallbitCredential.login_expires_at > datetime.now(timezone.utc),
        )
        .values(is_active=True, login_code_hash=None, login_expires_at=None)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        return False
    UserSettingsRepository().get_or_create(session, telegram_user_id)
    return True


def get_identity(session: Session, telegram_user_id: int) -> AccountIdentity | None:
    """Carga una cuenta activa sin conservar secretos en cachés globales.

    Args:
        session: Sesión de lectura.
        telegram_user_id: ID autenticado por Telegram.

    Returns:
        Cuenta descifrada, o None si no hay sesión activa.

    Raises:
        ValueError: Si el secreto del servidor no puede descifrar la credencial.
    """
    credential = session.get(WallbitCredential, telegram_user_id)
    if credential is None or not credential.is_active:
        return None
    try:
        api_key = credential_cipher().decrypt(credential.encrypted_api_key.encode()).decode()
    except InvalidToken as error:
        raise ValueError("No se pudo descifrar una credencial Wallbit; revisa la clave del servidor.") from error
    return AccountIdentity(telegram_user_id, SecretStr(api_key))


def logout(session: Session, telegram_user_id: int) -> None:
    """Desactiva la cuenta y sus automatizaciones sin borrar el historial.

    Args:
        session: Sesión del llamador; debe confirmar la transacción.
        telegram_user_id: Propietario que solicita desconectarse.

    Returns:
        None. Conserva la credencial cifrada para renovar la misma cuenta.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Si falla la revocación.
    """
    session.execute(update(WallbitCredential).where(WallbitCredential.telegram_user_id == telegram_user_id)
                    .values(is_active=False, login_code_hash=None, login_expires_at=None))
    user_ids = select(UserSettings.id).where(UserSettings.telegram_user_id == telegram_user_id)
    session.execute(update(DCARule).where(DCARule.user_id.in_(user_ids)).values(enabled=False))
    session.execute(update(Alert).where(Alert.user_id.in_(user_ids)).values(enabled=False))
    session.execute(update(PendingOrder).where(PendingOrder.user_id.in_(user_ids), PendingOrder.status == "pending")
                    .values(status="expired"))
