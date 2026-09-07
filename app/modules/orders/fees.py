"""Estimación transparente de tarifas publicadas por Wallbit."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.models import WallbitCredential
from app.modules.settings.models import UserSettings

PLAN_RATES = {
    "classic": Decimal("0.0040"),
    "pro": Decimal("0.0035"),
    "max": Decimal("0.0030"),
}
CENT = Decimal("0.01")
MAX_PLAN_FEE_CAP = Decimal("10.00")


@dataclass(frozen=True, slots=True)
class TradeFeeEstimate:
    """Importes redondeados a centavos para presentar y comprobar fondos."""

    plan: str
    rate: Decimal
    amount_usd: Decimal
    fee_usd: Decimal
    total_usd: Decimal


def estimate_trade_fee(session: Session, user: UserSettings, amount_usd: float) -> TradeFeeEstimate:
    """Estima la comisión según el plan configurado; Wallbit determina el cobro final.

    Args:
        session: Sesión usada para obtener el plan individual en modo multiusuario.
        user: Propietario de la orden.
        amount_usd: Importe base positivo de la compra en USD.

    Returns:
        Estimación monetaria a dos decimales y la tasa utilizada.

    Raises:
        ValueError: Si el importe no es positivo o el plan persistido es desconocido.
    """
    amount = Decimal(str(amount_usd))
    if not amount.is_finite() or amount <= 0:
        raise ValueError("El monto debe ser positivo y finito.")
    plan = settings.WALLBIT_PLAN
    if settings.MULTI_USER_ENABLED:
        credential = session.get(WallbitCredential, user.telegram_user_id)
        if credential is None or not credential.is_active:
            raise ValueError("La cuenta Wallbit no está vinculada.")
        plan = credential.wallbit_plan
    rate = PLAN_RATES.get(plan)
    if rate is None:
        raise ValueError("El plan Wallbit configurado no es válido.")
    fee = amount * rate
    if plan == "max":
        fee = min(fee, MAX_PLAN_FEE_CAP)
    fee = fee.quantize(CENT, rounding=ROUND_HALF_UP)
    rounded_amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return TradeFeeEstimate(
        plan=plan,
        rate=rate,
        amount_usd=rounded_amount,
        fee_usd=fee,
        total_usd=rounded_amount + fee,
    )


def format_fee_summary(estimate: TradeFeeEstimate, *, bold: bool = True) -> str:
    """Formatea monto, comisión estimada y total para Telegram.

    Args:
        estimate: Importes ya redondeados a centavos.
        bold: True aplica negrita HTML a los importes.

    Returns:
        Tres líneas listas para insertar en el mensaje de confirmación.
    """
    wrap = ("<b>", "</b>") if bold else ("", "")
    return (
        f"Monto: {wrap[0]}${estimate.amount_usd:,.2f} USD{wrap[1]}\n"
        f"Comisión estimada: {wrap[0]}${estimate.fee_usd:,.2f} USD{wrap[1]}\n"
        f"Total aproximado: {wrap[0]}${estimate.total_usd:,.2f} USD{wrap[1]}"
    )
