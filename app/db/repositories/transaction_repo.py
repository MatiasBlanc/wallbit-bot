"""Local transactions repository."""


from sqlalchemy.orm import Session

from app.db.models import LocalTransaction


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
        return session.query(LocalTransaction).filter(LocalTransaction.user_id == user_id).count()
