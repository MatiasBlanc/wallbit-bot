"""Tests for AlertService."""

import pytest

from app.core.constants import (
    ALERT_TYPE_FX,
    ALERT_TYPE_PRICE,
    OPERATOR_GTE,
    OPERATOR_LTE,
)
from app.modules.alerts.service import AlertService


@pytest.mark.parametrize("target", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_rejects_invalid_alert_target(alert_service: AlertService, db_session, test_user, target):
    with pytest.raises(ValueError, match="positivo y finito"):
        alert_service.create_alert(
            session=db_session,
            user=test_user,
            alert_type=ALERT_TYPE_PRICE,
            symbol="VOO",
            operator=OPERATOR_GTE,
            target_value=target,
        )


@pytest.mark.asyncio
async def test_create_and_trigger_price_alert_gte(alert_service: AlertService, db_session, test_user):
    # VOO is mocked at 495.20
    # Target 490 (>= 490 -> should trigger)
    alert = alert_service.create_alert(
        session=db_session,
        user=test_user,
        alert_type=ALERT_TYPE_PRICE,
        symbol="VOO",
        operator=OPERATOR_GTE,
        target_value=490.0,
    )
    db_session.commit()

    triggered = await alert_service.check_active_alerts(db_session)
    assert len(triggered) == 1
    assert triggered[0].alert.id == alert.id
    assert triggered[0].current_value == 495.20
    assert "VOO" in triggered[0].message
    assert "$495.20" in triggered[0].message

    # Check alert was disabled in DB
    refreshed = alert_service.alert_repo.get_by_id(db_session, alert.id)
    assert refreshed.triggered is True
    assert refreshed.enabled is False

    # Second check cycle: alert must not trigger again
    triggered_second = await alert_service.check_active_alerts(db_session)
    assert len(triggered_second) == 0


@pytest.mark.asyncio
async def test_alert_not_triggered_when_threshold_unmet(alert_service: AlertService, db_session, test_user):
    # AAPL is mocked at 180.00
    # Target 200 (>= 200 -> should NOT trigger)
    alert_service.create_alert(
        session=db_session,
        user=test_user,
        alert_type=ALERT_TYPE_PRICE,
        symbol="AAPL",
        operator=OPERATOR_GTE,
        target_value=200.0,
    )
    db_session.commit()

    triggered = await alert_service.check_active_alerts(db_session)
    assert len(triggered) == 0


@pytest.mark.asyncio
async def test_create_and_trigger_fx_alert_lte(alert_service: AlertService, db_session, test_user):
    # USD/CLP is mocked at 950.0
    # Target 960 (<= 960 -> should trigger)
    alert = alert_service.create_alert(
        session=db_session,
        user=test_user,
        alert_type=ALERT_TYPE_FX,
        symbol="USD/CLP",
        operator=OPERATOR_LTE,
        target_value=960.0,
    )
    db_session.commit()

    triggered = await alert_service.check_active_alerts(db_session)
    assert len(triggered) == 1
    assert triggered[0].alert.id == alert.id
    assert triggered[0].current_value == 950.0
