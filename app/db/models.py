"""SQLAlchemy ORM models."""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(BigInteger, unique=True, index=True, nullable=False)
    default_currency = Column(String(10), default="CLP", nullable=False)
    report_time = Column(String(5), default="09:00", nullable=False)
    timezone = Column(String(50), default="America/Santiago", nullable=False)
    alerts_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_daily_report = Column(String(10), nullable=True)  # Stores "YYYY-MM-DD" of last sent report

    dca_rules = relationship("DCARule", back_populates="user", cascade="all, delete-orphan")
    pending_orders = relationship("PendingOrder", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("LocalTransaction", back_populates="user", cascade="all, delete-orphan")


class DCARule(Base):
    __tablename__ = "dca_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_settings.id", ondelete="CASCADE"), nullable=False)
    ticker = Column(String(20), nullable=False)
    amount_usd = Column(Float, nullable=False)
    frequency = Column(String(20), nullable=False)  # "weekly", "monthly"
    weekday = Column(Integer, nullable=True)  # 0=Monday..6=Sunday
    day_of_month = Column(Integer, nullable=True)  # 1..31
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    next_execution_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("UserSettings", back_populates="dca_rules")
    pending_orders = relationship("PendingOrder", back_populates="dca_rule")


class PendingOrder(Base):
    __tablename__ = "pending_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_settings.id", ondelete="CASCADE"), nullable=False)
    dca_rule_id = Column(Integer, ForeignKey("dca_rules.id", ondelete="SET NULL"), nullable=True)
    ticker = Column(String(20), nullable=False)
    amount_usd = Column(Float, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending, confirmed, cancelled, expired, executed, failed
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    external_order_id = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=False)

    user = relationship("UserSettings", back_populates="pending_orders")
    dca_rule = relationship("DCARule", back_populates="pending_orders")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_settings.id", ondelete="CASCADE"), nullable=False)
    alert_type = Column(String(20), nullable=False)  # "price", "exchange_rate"
    symbol = Column(String(30), nullable=False)  # e.g. "VOO", "USD/CLP"
    operator = Column(String(5), nullable=False)  # ">=", "<="
    target_value = Column(Float, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    triggered = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("UserSettings", back_populates="alerts")


class LocalTransaction(Base):
    __tablename__ = "local_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_settings.id", ondelete="CASCADE"), nullable=False)
    transaction_type = Column(String(20), nullable=False)  # BUY, SELL, DEPOSIT, WITHDRAWAL, DCA_BUY
    ticker = Column(String(20), nullable=True)
    amount_usd = Column(Float, nullable=False)
    external_order_id = Column(String(100), nullable=True)
    source = Column(String(20), default="MANUAL", nullable=False)  # WALLBIT, DCA, MANUAL
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("UserSettings", back_populates="transactions")
