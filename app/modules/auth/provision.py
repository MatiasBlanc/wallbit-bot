"""Alta local: python -m app.modules.auth.provision --telegram-user-id ID [--renew]."""

import argparse
import asyncio
from getpass import getpass

from pydantic import SecretStr

from app.core.config import settings
from app.core.identity import AccountIdentity, account_scope
from app.infrastructure.database.database import get_db_session, init_db
from app.infrastructure.wallbit.client import WallbitClient
from app.modules.auth.service import issue_login_code, validate_multi_user_config


async def provision(telegram_user_id: int, should_renew: bool, wallbit_plan: str) -> str:
    """Valida una API key introducida sin eco y emite un código de vinculación.

    Args:
        telegram_user_id: Destinatario del código, identificado previamente en Telegram.
        should_renew: True reutiliza la credencial cifrada sin sustituir la cuenta.
        wallbit_plan: Plan usado para estimar la comisión mostrada antes de confirmar.

    Returns:
        Código temporal para entregar al destinatario por un canal privado.

    Raises:
        ValueError: Si falta configuración, la cuenta no es válida o falla la conexión.
        sqlalchemy.exc.SQLAlchemyError: Si falla la persistencia.
    """
    if not settings.MULTI_USER_ENABLED:
        raise ValueError("Configura MULTI_USER_ENABLED=true antes de vincular cuentas.")
    validate_multi_user_config()
    if telegram_user_id <= 0:
        raise ValueError("El ID de Telegram debe ser positivo.")
    init_db()
    api_key = None
    if not should_renew:
        api_key = SecretStr(getpass("API key de Wallbit (entrada oculta; no se envía a Telegram): ").strip())
        if not api_key.get_secret_value():
            raise ValueError("La API key no puede estar vacía.")
        with account_scope(AccountIdentity(telegram_user_id, api_key)):
            async with WallbitClient() as client:
                if not await client.check_connection():
                    raise ValueError("No se pudo validar la API key con Wallbit. No se creó la cuenta.")
    with get_db_session() as session:
        if should_renew:
            from app.modules.auth.models import WallbitCredential
            if session.get(WallbitCredential, telegram_user_id) is None:
                raise ValueError("La cuenta no existe; realiza el alta sin --renew.")
        return issue_login_code(session, telegram_user_id, api_key, wallbit_plan)


def main() -> None:
    """Ejecuta el alta desde una terminal privada del administrador.

    Returns:
        None. Muestra únicamente el código temporal, nunca la API key.

    Raises:
        SystemExit: Si los argumentos o la configuración son inválidos.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--telegram-user-id", type=int, required=True)
    parser.add_argument("--renew", action="store_true")
    parser.add_argument("--plan", choices=["classic", "pro", "max"], default="classic")
    args = parser.parse_args()
    try:
        code = asyncio.run(provision(args.telegram_user_id, args.renew, args.plan))
    except ValueError as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Código exclusivo para Telegram ID {args.telegram_user_id}; vence en {settings.LOGIN_CODE_TTL_MINUTES} minutos.")
    print(f"Entregar por canal privado: /login {code}")


if __name__ == "__main__":
    main()
