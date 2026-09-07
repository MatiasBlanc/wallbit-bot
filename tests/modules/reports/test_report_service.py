"""Tests for ReportService."""

import pytest

from app.core.constants import TX_TYPE_BUY
from app.modules.history.models import LocalTransaction
from app.modules.reports.service import ReportService


@pytest.mark.asyncio
async def test_generate_report(report_service: ReportService, db_session, test_user):
    # Record local buys so ROI is computed:
    # VOO: cost $400, current $495.20 -> +23.8%
    # AAPL: cost $400, current $360.00 -> -10%
    tx1 = LocalTransaction(
        user_id=test_user.id,
        transaction_type=TX_TYPE_BUY,
        amount_usd=400.0,
        ticker="VOO",
        source="TEST",
    )
    tx2 = LocalTransaction(
        user_id=test_user.id,
        transaction_type=TX_TYPE_BUY,
        amount_usd=400.0,
        ticker="AAPL",
        source="TEST",
    )
    db_session.add_all([tx1, tx2])
    db_session.commit()

    report = await report_service.generate_report(db_session, test_user)

    assert abs(report.available_balance_usd - 305.70) < 1e-4
    assert abs(report.total_investments_usd - 855.20) < 1e-4
    assert report.best_position_ticker == "VOO"
    assert report.worst_position_ticker == "AAPL"
    assert report.fx_pair == "USD/CLP"
    assert report.fx_rate == 950.0

    msg = report.to_telegram_message()
    assert "Resumen" in msg
    assert "$305.70 USD" in msg
    assert "$855.20 USD" in msg
    assert "VOO" in msg
    assert "AAPL" in msg
