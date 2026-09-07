-- Esquema SQLite anterior a la organización por dominios.
CREATE TABLE user_settings (
    id INTEGER NOT NULL,
    telegram_user_id BIGINT NOT NULL,
    default_currency VARCHAR(10) NOT NULL,
    report_time VARCHAR(5) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    alerts_enabled BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    last_daily_report VARCHAR(10),
    PRIMARY KEY (id)
);
CREATE INDEX ix_user_settings_id ON user_settings (id);
CREATE UNIQUE INDEX ix_user_settings_telegram_user_id ON user_settings (telegram_user_id);
CREATE TABLE alerts (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    alert_type VARCHAR(20) NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    operator VARCHAR(5) NOT NULL,
    target_value FLOAT NOT NULL,
    enabled BOOLEAN NOT NULL,
    triggered BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    triggered_at DATETIME,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES user_settings (id) ON DELETE CASCADE
);
CREATE INDEX ix_alerts_id ON alerts (id);
CREATE TABLE dca_rules (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    amount_usd FLOAT NOT NULL,
    frequency VARCHAR(20) NOT NULL,
    weekday INTEGER,
    day_of_month INTEGER,
    enabled BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    last_triggered_at DATETIME,
    next_execution_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES user_settings (id) ON DELETE CASCADE
);
CREATE INDEX ix_dca_rules_id ON dca_rules (id);
CREATE TABLE local_transactions (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    transaction_type VARCHAR(20) NOT NULL,
    ticker VARCHAR(20),
    amount_usd FLOAT NOT NULL,
    external_order_id VARCHAR(100),
    source VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES user_settings (id) ON DELETE CASCADE
);
CREATE INDEX ix_local_transactions_id ON local_transactions (id);
CREATE TABLE pending_orders (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    dca_rule_id INTEGER,
    ticker VARCHAR(20) NOT NULL,
    amount_usd FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    executed_at DATETIME,
    external_order_id VARCHAR(100),
    idempotency_key VARCHAR(100) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES user_settings (id) ON DELETE CASCADE,
    FOREIGN KEY(dca_rule_id) REFERENCES dca_rules (id) ON DELETE SET NULL
);
CREATE INDEX ix_pending_orders_id ON pending_orders (id);
CREATE UNIQUE INDEX ix_pending_orders_idempotency_key ON pending_orders (idempotency_key);
