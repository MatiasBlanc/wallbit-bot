"""Benchmark local reproducible: HTTP simulado, SQLite en memoria y cero órdenes reales.

Uso: python benchmarks/benchmark.py [--source-root /ruta/a/otra/version]
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import tracemalloc
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument("--positions", type=int, default=20)
parser.add_argument("--transactions", type=int, default=200, help="Compras locales por posición")
parser.add_argument("--latency-ms", type=float, default=10)
parser.add_argument("--runs", type=int, default=3)
args = parser.parse_args()
if min(args.positions, args.transactions, args.runs) < 1 or args.latency_ms < 0:
    parser.error("Los tamaños deben ser positivos y la latencia no negativa.")
sys.path.insert(0, str(args.source_root.resolve()))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TRADING_ENABLED"] = "false"
os.environ["MULTI_USER_ENABLED"] = "false"
os.environ["TELEGRAM_ALLOWED_USER_ID"] = "123456789"

import httpx
from sqlalchemy import event, insert

from app.infrastructure.database.database import SessionLocal, engine, init_db
from app.infrastructure.wallbit.client import WallbitClient
from app.modules.balance.service import BalanceService
from app.modules.dca.jobs import run_dca_checker
from app.modules.dca.repository import DCARuleRepository
from app.modules.dca.service import DCAService
from app.modules.history.models import LocalTransaction
from app.modules.history.repository import LocalTransactionRepository
from app.modules.orders.jobs import run_order_expiration_check
from app.modules.orders.repository import PendingOrderRepository
from app.modules.orders.service import OrderService
from app.modules.portfolio.service import PortfolioService
from app.modules.reports.service import ReportService
from app.modules.settings.repository import UserSettingsRepository
from app.shared.exchange.providers import WallbitExchangeRateProvider
from app.shared.exchange.service import ExchangeRateService


async def main() -> None:
    """Mide latencia mediana, memoria Python, solicitudes HTTP y sentencias SQL.

    Returns:
        None. Imprime un documento JSON con las mediciones locales.
    """
    init_db()
    http_calls: Counter[str] = Counter()
    sql_calls = 0
    active = 0
    peak_active = 0

    def count_sql(*_args) -> None:
        nonlocal sql_calls
        sql_calls += 1

    async def respond(request: httpx.Request) -> httpx.Response:
        nonlocal active, peak_active
        assert request.method == "GET", "El benchmark nunca debe enviar una compra real."
        http_calls[request.url.path] += 1
        active += 1
        peak_active = max(peak_active, active)
        try:
            await asyncio.sleep(args.latency_ms / 1000)
            path = request.url.path
            if path.endswith("/balance/checking"):
                data = [{"currency": "USD", "balance": 1000.0}]
            elif path.endswith("/balance/stocks"):
                data = [{"symbol": "USD", "shares": 1000.0}] + [
                    {"symbol": f"T{i}", "shares": 10.0} for i in range(args.positions)
                ]
            elif "/assets/" in path:
                symbol = path.rsplit("/", 1)[1]
                data = {"symbol": symbol, "name": symbol, "price": 100.0}
            elif path.endswith("/rates"):
                data = {"source_currency": "USD", "dest_currency": "CLP", "pair": "USDCLP", "rate": 950.0}
            else:
                raise AssertionError(f"Endpoint inesperado: {path}")
            return httpx.Response(200, json={"data": data})
        finally:
            active -= 1

    event.listen(engine, "before_cursor_execute", count_sql)
    async with WallbitClient(base_url="https://benchmark.invalid", api_key="") as client:
        client._client = httpx.AsyncClient(base_url=client.base_url, transport=httpx.MockTransport(respond))
        exchange = ExchangeRateService(WallbitExchangeRateProvider(client), cache_ttl_seconds=0)
        balance = BalanceService(client, exchange)
        portfolio = PortfolioService(client)
        reports = ReportService(balance, portfolio, exchange)
        orders_repo = PendingOrderRepository()
        orders = OrderService(orders_repo, LocalTransactionRepository(), client, balance)
        dca = DCAService(DCARuleRepository(), orders, client, balance)
        with SessionLocal() as session:
            user = UserSettingsRepository().get_or_create(session, 123456789)
            session.execute(insert(LocalTransaction), [
                {"user_id": user.id, "transaction_type": "BUY", "amount_usd": 5.0, "ticker": f"T{i}", "source": "TEST"}
                for i in range(args.positions) for _ in range(args.transactions)
            ])
            session.commit()
            results = {}
            async def unbatched_dca(rules) -> None:
                """Referencia: consulta fondos y precio para cada regla individual."""
                for rule in rules:
                    await dca.trigger_dca_rule(session, rule, user)
                    session.commit()

            for scenario in ("balance", "portfolio", "report", "confirm", "dca", "expiration", "dca_unbatched_10", "dca_batched_10"):
                durations, peaks = [], []
                for run in range(args.runs):
                    if scenario.startswith("dca_"):
                        rules = []
                        for _ in range(10):
                            rule = dca.create_rule(session, user, "T0", 50.0, "weekly", weekday=0)
                            rule.next_execution_at = datetime.now(timezone.utc) - timedelta(minutes=1)
                            rules.append(rule)
                        session.commit()
                        operation = (
                            unbatched_dca(rules) if scenario == "dca_unbatched_10"
                            else run_dca_checker(AsyncMock(), dca)
                        )
                    elif scenario == "confirm":
                        order = orders.create_pending_order(session, user, "T0", 50.0)
                        session.commit()
                        operation = orders.confirm_order(session, order.id, user)
                    elif scenario == "dca":
                        rule = dca.create_rule(session, user, "T0", 50.0, "weekly", weekday=0)
                        session.commit()
                        operation = dca.trigger_dca_rule(session, rule, user)
                    elif scenario == "expiration":
                        for i in range(200):
                            orders_repo.create(session, user.id, "T0", 50.0,
                                               datetime.now(timezone.utc) - timedelta(hours=1), f"expired-{run}-{i}")
                        session.commit()
                        operation = run_order_expiration_check(orders_repo)
                    elif scenario == "balance":
                        operation = balance.get_balance()
                    elif scenario == "portfolio":
                        operation = portfolio.get_portfolio(session, user.id)
                    else:
                        operation = reports.generate_report(session, user)
                    http_calls.clear()
                    sql_calls = peak_active = 0
                    tracemalloc.start()
                    started = time.perf_counter()
                    await operation
                    durations.append((time.perf_counter() - started) * 1000)
                    _, peak = tracemalloc.get_traced_memory()
                    tracemalloc.stop()
                    peaks.append(peak / 1024)
                    session.commit()
                results[scenario] = {
                    "median_ms": round(statistics.median(durations), 2),
                    "peak_python_kib": round(max(peaks), 2),
                    "http_requests_last_run": sum(http_calls.values()),
                    "sql_statements_last_run": sql_calls,
                    "max_concurrent_http_last_run": peak_active,
                }
    event.remove(engine, "before_cursor_execute", count_sql)
    engine.dispose()
    print(json.dumps({"positions": args.positions, "transactions_per_position": args.transactions,
                      "simulated_http_latency_ms": args.latency_ms, "runs": args.runs, "results": results}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
