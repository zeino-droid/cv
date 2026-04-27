"""Helpers communs aux clients de sourcing."""

from __future__ import annotations

import hashlib


def stable_id(prefix: str, *parts) -> str:
    """ID stable basé sur un hash MD5 court (12 chars) — idempotent."""
    raw = "|".join(str(p).strip().lower() for p in parts if p is not None)
    digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"
