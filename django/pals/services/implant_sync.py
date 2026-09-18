"""Read only the implant items from a decoded Palworld save."""

from __future__ import annotations

import json
from pathlib import Path

from .data import IMPLANT_INVENTORY_FILE, PARSER_ASSETS, SKILL_METADATA


def _item_names() -> dict[str, str]:
    path = PARSER_ASSETS / "items.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")).get("en", [])
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(item.get("id", "")).lower(): str(item.get("name", "")).strip()
        for item in data
        if isinstance(item, dict) and item.get("id") and item.get("name")
    }


def _passive_names() -> set[str]:
    try:
        data = json.loads(SKILL_METADATA.read_text(encoding="utf-8")).get("en", {})
    except (OSError, json.JSONDecodeError):
        return set()
    return {
        str(skill.get("name", "")).strip()
        for skill in data.values()
        if isinstance(skill, dict) and str(skill.get("name", "")).strip()
    }


def _passive_name(item_id: str, item_names: dict[str, str], passive_names: set[str]) -> str:
    label = item_names.get(item_id.lower(), "")
    for prefix in ("Disposable Implant: ", "Implant: "):
        if label.startswith(prefix):
            name = label[len(prefix):].strip()
            if name in passive_names:
                return name
    return ""


def _existing_inventory() -> dict:
    try:
        data = json.loads(IMPLANT_INVENTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def sync_implant_inventory(level_json: Path) -> dict:
    """Merge save-derived implants into the small app inventory.

    Only item IDs beginning with ``palpassiveskillchange_`` are examined. The
    existing infinite entries are retained for surgery-table defaults and the
    finite disposable counts are replaced by the decoded save counts.
    """
    try:
        decoded = json.loads(level_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"ok": False, "error": f"Could not read decoded save: {error}"}

    world = decoded.get("properties", {}).get("worldSaveData", {}).get("value", {})
    item_names = _item_names()
    passive_names = _passive_names()
    finite: dict[str, int] = {}
    infinite: set[str] = set()

    for container in world.get("ItemContainerSaveData", {}).get("value", []):
        slots = container.get("value", {}).get("Slots", {}).get("value", {}).get("values", [])
        for slot in slots:
            raw = slot.get("RawData", {}).get("value") or {}
            item = raw.get("item") or {}
            item_id = str(item.get("static_id") or "").lower()
            if not item_id.startswith("palpassiveskillchange_"):
                continue
            passive = _passive_name(item_id, item_names, passive_names)
            if not passive:
                continue
            if item_id.startswith("palpassiveskillchange_consumable_"):
                finite[passive] = finite.get(passive, 0) + max(0, int(raw.get("count") or 0))
            else:
                infinite.add(passive)

    existing = _existing_inventory()
    inventory = {
        passive: {"infinite": True, "count": None}
        for passive, item in existing.items()
        if isinstance(item, dict) and item.get("infinite")
    }
    for passive in infinite:
        inventory[passive] = {"infinite": True, "count": None}
    for passive, count in finite.items():
        if passive not in inventory:
            inventory[passive] = {"infinite": False, "count": count}

    IMPLANT_INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    IMPLANT_INVENTORY_FILE.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "infiniteCount": sum(1 for item in inventory.values() if item.get("infinite")),
        "finite": finite,
        "inventory": inventory,
    }
