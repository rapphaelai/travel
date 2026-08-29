"""Persistenta simpla, pe fisiere JSON -- un fisier per "context de excursie"
in data/contexts/<id>.json. Suficient pentru un tool personal, cu un singur
utilizator; nu e gandit pentru concurenta multi-user."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "contexts"
MEDIA_DIR = REPO_ROOT / "assets" / "output" / "web"

_lock = threading.Lock()


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _path(context_id: str) -> Path:
    return DATA_DIR / f"{context_id}.json"


def save_context(data: dict[str, Any]) -> None:
    _ensure_dirs()
    with _lock:
        _path(data["id"]).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_context(context_id: str) -> dict[str, Any] | None:
    p = _path(context_id)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_contexts() -> list[dict[str, Any]]:
    _ensure_dirs()
    items = []
    for p in sorted(DATA_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return items


def delete_context(context_id: str) -> bool:
    p = _path(context_id)
    if p.exists():
        p.unlink()
        return True
    return False


def context_media_dir(context_id: str) -> Path:
    d = MEDIA_DIR / context_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
