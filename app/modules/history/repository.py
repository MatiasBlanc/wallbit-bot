"""Local transactions repository."""


from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import TX_TYPE_BUY, TX_TYPE_DCA_BUY
from app.modules.history.models import LocalTransaction


class LocalTransactionRepository:
    def create(
        self,
        session: Session,
        user_id: int,
        transaction_type: str,
        amount_usd: float,
        ticker: str = None,
        external_order_id: str = None,
        source: str = "MANUAL",
    ) -> LocalTransaction:
        tx = LocalTransaction(
            user_id=user_id,
            transaction_type=transaction_type,
            amount_usd=amount_usd,
            ticker=ticker.upper() if ticker else None,
            external_order_id=external_order_id,
            source=source,
        )
        session.add(tx)
        session.flush()
        return tx

    def list_by_user(
        self,
        session: Session,
        user_id: int,
        limit: int = 10,
        offset: int = 0,
    ) -> list[LocalTransaction]:
        return (
            session.query(LocalTransaction)
            .filter(LocalTransaction.user_id == user_id)
            .order_by(LocalTransaction.created_at.desc(), LocalTransaction.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_by_user(self, session: Session, user_id: int) -> int:
        return session.scalar(
            select(func.count()).select_from(LocalTransaction).where(LocalTransaction.user_id == user_id)
        ) or 0

    def get_cost_basis_by_ticker(
        self, session: Session, user_id: int, tickers: list[str],
    ) -> dict[str, float]:
        """Agrega compras locales en SQL, sin hidratar todo el historial.

        Args:
            session: Sesión de lectura del llamador.
            user_id: Propietario de los movimientos.
            tickers: Posiciones a valorar.

        Returns:
            Importes positivos agrupados por ticker; ausencia significa costo desconocido.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: Si falla la consulta.
        """
        if not tickers:
            return {}
        statement = (
            select(LocalTransaction.ticker, func.sum(LocalTransaction.amount_usd))
            .where(
                LocalTransaction.user_id == user_id,
                LocalTransaction.ticker.in_(tickers),
                LocalTransaction.transaction_type.in_([TX_TYPE_BUY, TX_TYPE_DCA_BUY]),
            )
            .group_by(LocalTransaction.ticker)
        )
        return {ticker: total for ticker, total in session.execute(statement) if total is not None and total > 0}
