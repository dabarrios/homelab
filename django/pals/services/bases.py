"""Base planning persistence helpers."""

from __future__ import annotations

import json

from .data import BASE_LABELS_FILE


def load_base_labels() -> dict:
    if not BASE_LABELS_FILE.exists():
        return {}
    try:
        data = json.loads(BASE_LABELS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_base_labels(labels: dict) -> None:
    BASE_LABELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASE_LABELS_FILE.write_text(json.dumps(labels, indent=2, sort_keys=True), encoding="utf-8")


def module_status() -> dict[str, str]:
    return {"state": "partial", "message": "Base label persistence is imported; planner extraction is still pending."}
