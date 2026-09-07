"""DCA delega la intención de compra sin ejecutar la orden."""

from unittest.mock import patch

import pytest

from app.core.constants import DCA_FREQ_WEEKLY


@pytest.mark.parametrize("amount, has_funds", [(50.0, True), (1000.0, False)])
async def test_dca_delegates_pending_order_creation(
    dca_service, order_service, db_session, test_user, mock_wallbit_client, amount, has_funds,
):
    rule = dca_service.create_rule(
        db_session, test_user, "VOO", amount, DCA_FREQ_WEEKLY, weekday=0,
    )
    with patch.object(order_service, "create_pending_order", wraps=order_service.create_pending_order) as create:
        result, order, _, _ = await dca_service.trigger_dca_rule(db_session, rule, test_user)

    assert result is has_funds
    if has_funds:
        create.assert_called_once_with(
            session=db_session, user=test_user, ticker="VOO", amount_usd=amount, dca_rule_id=rule.id,
        )
        assert order.dca_rule_id == rule.id
        assert order.idempotency_key.startswith(f"dca-{rule.id}-")
    else:
        create.assert_not_called()
        assert order is None
    assert rule.last_triggered_at is not None
    assert rule.next_execution_at > rule.last_triggered_at
    mock_wallbit_client.create_trade.assert_not_called()
