from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AppError(Exception):
    """Represent an expected API error that is safe to return to clients."""

    code: str
    message: str
    status_code: int
