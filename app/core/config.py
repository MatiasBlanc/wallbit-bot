"""Application configuration and settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Telegram
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram Bot API Token")
    TELEGRAM_ALLOWED_USER_ID: int = Field(default=0, description="Authorized Telegram User ID")

    # Wallbit API
    WALLBIT_API_KEY: str = Field(default="", description="Wallbit Public API Key")
    WALLBIT_BASE_URL: str = Field(default="https://api.wallbit.io", description="Wallbit API Base URL")

    # Database
    DATABASE_URL: str = Field(default="sqlite:///wallbit.db", description="Database connection URL")

    # User Defaults
    DEFAULT_CURRENCY: str = Field(default="CLP", description="Default currency code (e.g. CLP, USD, ARS, EUR, USDC)")
    DEFAULT_TIMEZONE: str = Field(default="America/Santiago", description="Default user timezone")
    DEFAULT_REPORT_TIME: str = Field(default="09:00", description="Daily morning report time (HH:MM)")

    # Trading & Simulation
    TRADING_ENABLED: bool = Field(default=False, description="When false, all trades run in simulation/dry-run mode")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Scheduler intervals (minutes)
    ALERT_CHECK_INTERVAL_MINUTES: int = Field(default=5, description="Interval to check price and FX alerts")
    DCA_CHECK_INTERVAL_MINUTES: int = Field(default=1, description="Interval to check due DCA rules")
    ORDER_EXPIRY_HOURS: int = Field(default=24, description="Hours until an unconfirmed pending order expires")

    @field_validator("DEFAULT_REPORT_TIME")
    @classmethod
    def validate_report_time(cls, v: str) -> str:
        parts = v.strip().split(":")
        if len(parts) != 2:
            raise ValueError("report_time must be in HH:MM format")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("report_time must have hours 00-23 and minutes 00-59")
        return f"{h:02d}:{m:02d}"


settings = Settings()
