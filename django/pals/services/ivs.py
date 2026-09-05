"""IV planning and implant inventory helpers."""

from __future__ import annotations

import json

from .data import IMPLANT_INVENTORY_FILE, as_int


def load_implant_inventory() -> dict:
    if not IMPLANT_INVENTORY_FILE.exists():
        return {}
    try:
        data = json.loads(IMPLANT_INVENTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    inventory = {}
    for passive, item in data.items():
        if not isinstance(item, dict):
            continue
        name = str(passive or "").strip()
        if not name:
            continue
        inventory[name] = {
            "infinite": bool(item.get("infinite")),
            "count": max(0, as_int(item.get("count"))) if not item.get("infinite") else None,
        }
    return inventory


def available_implant_passives() -> set[str]:
    return {
        passive
        for passive, item in load_implant_inventory().items()
        if item.get("infinite") or as_int(item.get("count")) > 0
    }


def save_implant_inventory(inventory: dict) -> None:
    IMPLANT_INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    IMPLANT_INVENTORY_FILE.write_text(json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8")


def module_status() -> dict[str, str]:
    return {"state": "partial", "message": "Implant inventory is imported; IV planner extraction is still pending."}
