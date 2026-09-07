"""Logging setup with secret sanitization."""

import logging
import re

from app.core.config import settings
from app.core.identity import current_identity


class SecretSanitizingFilter(logging.Filter):
    """Filter that sanitizes sensitive values from log messages."""

    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self.secrets = [s for s in (secrets or []) if s and len(s) > 4]
        # Regex patterns for common secret formats
        self.patterns = [
            (re.compile(r"([X-]*API[-_]?Key[:=\s]+)[A-Za-z0-9_\-\.]{8,}", re.IGNORECASE), r"\1***REDACTED***"),
            (re.compile(r"(bot[0-9]{8,10}:)[A-Za-z0-9_\-]{30,}", re.IGNORECASE), r"\1***REDACTED***"),
            (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", re.IGNORECASE), r"\1***REDACTED***"),
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern, repl in self.patterns:
                msg = pattern.sub(repl, msg)
            for secret in self.secrets:
                if secret in msg:
                    msg = msg.replace(secret, "***REDACTED***")
            record.msg = msg

        # Also sanitize args if formatted
        if record.args:
            sanitized_args = []
            if isinstance(record.args, tuple):
                for arg in record.args:
                    if isinstance(arg, str):
                        for pattern, repl in self.patterns:
                            arg = pattern.sub(repl, arg)
                        for secret in self.secrets:
                            if secret in arg:
                                arg = arg.replace(secret, "***REDACTED***")
                    sanitized_args.append(arg)
                record.args = tuple(sanitized_args)
            elif isinstance(record.args, dict):
                sanitized_dict = {}
                for k, arg in record.args.items():
                    if isinstance(arg, str):
                        for pattern, repl in self.patterns:
                            arg = pattern.sub(repl, arg)
                        for secret in self.secrets:
                            if secret in arg:
                                arg = arg.replace(secret, "***REDACTED***")
                    sanitized_dict[k] = arg
                record.args = sanitized_dict
        return True


class SecretSanitizingFormatter(logging.Formatter):
    """Sanitiza el texto final, incluidos tracebacks y objetos anidados."""

    def __init__(self, delegate: logging.Formatter, secrets: list[str]) -> None:
        super().__init__()
        self.delegate = delegate
        self.sanitizer = SecretSanitizingFilter(secrets)

    def format(self, record: logging.LogRecord) -> str:
        """Formatea y elimina secretos antes de escribir en el destino.

        Args:
            record: Registro original, que puede incluir una excepción.

        Returns:
            Texto sin secretos globales ni la credencial de la tarea actual.
        """
        text = self.delegate.format(record)
        identity = current_identity.get()
        secrets = self.sanitizer.secrets.copy()
        if identity is not None:
            secrets.append(identity.api_key.get_secret_value())
        for secret in secrets:
            if secret:
                text = text.replace(secret, "***REDACTED***")
        for pattern, replacement in self.sanitizer.patterns:
            text = pattern.sub(replacement, text)
        return text


def setup_logging() -> None:
    """Configures application-wide logging."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if called multiple times
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Add secret sanitizing filter
    secrets_to_scrub = [
        settings.TELEGRAM_BOT_TOKEN, settings.WALLBIT_API_KEY,
        settings.CREDENTIAL_ENCRYPTION_KEY.get_secret_value(),
    ]
    if settings.AI_API_KEY:
        secrets_to_scrub.append(settings.AI_API_KEY)
    sanitizing_filter = SecretSanitizingFilter(secrets=secrets_to_scrub)

    for h in root_logger.handlers:
        h.addFilter(sanitizing_filter)
        if not isinstance(h.formatter, SecretSanitizingFormatter):
            h.setFormatter(SecretSanitizingFormatter(h.formatter or logging.Formatter(), secrets_to_scrub))

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(name)
