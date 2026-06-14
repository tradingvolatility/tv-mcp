"""Logging configuration.

Structured, level-controlled logging. Credentials are never logged anywhere in the codebase
(the API key is masked in ``Credential`` and never interpolated into messages), so this
config needs no redaction filter — it just standardizes the format and level.
"""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once, from a level name."""
    logging.basicConfig(level=level.upper(), format=_FORMAT)
