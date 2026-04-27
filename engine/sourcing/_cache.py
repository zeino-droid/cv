"""
Cache disque léger (24 h par défaut) — utilisé par France Travail et Adzuna
pour éviter de cramer les quotas et accélérer les recherches répétées.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).parent.parent.parent
CACHE_DIR = ROOT / "storage" / "sourcing_cache"


def _cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()
    sub = CACHE_DIR / namespace
    sub.mkdir(parents=True, exist_ok=True)
    return sub / f"{digest}.json"


def get_cache(namespace: str, key: str, ttl_seconds: int = 86400) -> Optional[Any]:
    """Retourne la valeur cachée si elle est encore fraîche, sinon None."""
    path = _cache_path(namespace, key)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if (time.time() - payload.get("ts", 0)) > ttl_seconds:
            return None
        return payload.get("data")
    except Exception:
        return None


def set_cache(namespace: str, key: str, data: Any) -> None:
    """Sauvegarde une valeur en cache (overwrite)."""
    path = _cache_path(namespace, key)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "data": data}, f, ensure_ascii=False)
    except Exception as exc:
        print(f"   ⚠️  Cache write failed ({namespace}): {exc}")
