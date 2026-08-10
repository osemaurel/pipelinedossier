"""Journalisation applicative. Ne journalise jamais de secret."""

from __future__ import annotations

import logging
import re
import sys

_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


class SecretFilter(logging.Filter):
    """Masque toute clé de type `sk-...` qui se glisserait dans un message."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _SECRET_PATTERN.sub("sk-***", record.msg)
        if record.args:
            record.args = tuple(
                _SECRET_PATTERN.sub("sk-***", a) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s %(name)s — %(message)s",
                                           datefmt="%H:%M:%S"))
    handler.addFilter(SecretFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
