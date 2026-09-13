"""Read-only effigy progress and map marker data."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .data import DATA_ROOT, STORE, WORK

ROOT = Path(__file__).resolve().parents[1]
MARKERS_FILE = ROOT / "reference_data" / "effigy_map" / "markers.json"
PERSISTED_PLAYERS = DATA_ROOT / "effigy_players"
GUID_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
IMAGE_SIZE = 8192
MAPS = {
    "palpagos": {
        "name": "Palpagos",
        "image": "T_WorldMap.png",
        "minX": -1099401,
        "maxX": 349385,
        "minY": -724397,
        "maxY": 724389,
        "div": 459,
        "offY": -158000,
        "offX": 123888,
    },
    "worldTree": {
        "name": "World Tree",
        "image": "T_TreeMap.png",
        "minX": 347350,
        "maxX": 689148,
        "minY": -818197,
        "maxY": -476399,
        "div": 1334,
        "offY": 647509,
        "offX": 517733,
    },
}


def _unwrap(value):
    while isinstance(value, dict) and set(value) == {"value"}:
        value = value["value"]
    return value


def _guid_key(value) -> str:
    text = str(value or "").lower()
    if GUID_RE.match(text):
        return text.replace("-", "")
    return text


def _record_data(payload: dict) -> dict:
    save_data = payload.get("properties", {}).get("SaveData", {})
    if isinstance(save_data, dict) and "value" in save_data:
        save_data = save_data["value"]
    record = save_data.get("RecordData", {}) if isinstance(save_data, dict) else {}
    if isinstance(record, dict) and isinstance(record.get("value"), dict):
        return record["value"]
    return _unwrap(record) if isinstance(record, dict) else {}


def _record_keys(entry) -> set[str]:
    entry = _unwrap(entry)
    result = set()
    if isinstance(entry, dict):
        if "key" in entry and entry.get("value") is True:
            result.add(_guid_key(entry["key"]))
        if "Flags" in entry:
            result.update(_record_keys(entry["Flags"]))
        if "values" in entry:
            result.update(_record_keys(entry["values"]))
        if "value" in entry and not ("key" in entry and entry.get("value") is True):
            result.update(_record_keys(entry["value"]))
        return result
    if not isinstance(entry, list):
        return result
    for item in entry:
        item = _unwrap(item)
        if isinstance(item, list) and len(item) > 1 and item[1] is True:
            result.add(_guid_key(item[0]))
        elif isinstance(item, dict):
            result.update(_record_keys(item))
    return result


def _player_files() -> list[Path]:
    persisted = list(PERSISTED_PLAYERS.glob("*.json")) if PERSISTED_PLAYERS.exists() else []
    players = PERSISTED_PLAYERS if persisted else WORK / "Players"
    if not players.exists():
        return []
    return sorted(p for p in players.glob("*.json") if p.name.lower() != "structure.json" and not p.name.lower().endswith("_dps.json"))


def _player_labels(players_dir: Path) -> dict[str, str]:
    structure = players_dir / "structure.json"
    if not structure.exists() and players_dir != WORK / "Players":
        structure = WORK / "structure.json"
    if not structure.exists():
        return {}
    try:
        entries = json.loads(structure.read_text(encoding="utf-8")).get("players", [])
    except (OSError, json.JSONDecodeError):
        return {}
    labels = {}
    for entry in entries:
        try:
            stem = f"{int(entry['player_uid']):08x}" + "0" * 24
            labels[stem.lower()] = str(entry.get("nickname") or "").strip()
        except (KeyError, TypeError, ValueError):
            continue
    return labels


def _display_player_label(player_id: str, labels: dict[str, str]) -> str:
    label = labels.get(player_id.lower(), "").strip()
    if label:
        return label
    # Match the other PALS sections when the save contains one known owner but
    # the optional structure metadata is unavailable.
    owners = [owner for owner in STORE.owners if owner]
    if len(owners) == 1:
        return owners[0]
    return f"Player {player_id[:8]}"


def _map_for(marker: dict) -> tuple[str, dict]:
    if marker["x"] >= 400000 and marker["y"] <= -500000:
        return "worldTree", MAPS["worldTree"]
    return "palpagos", MAPS["palpagos"]


def _marker_payload(marker: dict, collected: set[str]) -> dict:
    map_id, map_data = _map_for(marker)
    x = float(marker.get("x", 0))
    y = float(marker.get("y", 0))
    left = (y - map_data["minY"]) / (map_data["maxY"] - map_data["minY"]) * 100
    top = (map_data["maxX"] - x) / (map_data["maxX"] - map_data["minX"]) * 100
    map_x = round((y + map_data["offY"]) / map_data["div"])
    map_y = round((x + map_data["offX"]) / map_data["div"])
    key = _guid_key(marker.get("key"))
    return {
        "id": marker.get("id"),
        "key": key,
        "label": marker.get("label", "Effigy"),
        "category": marker.get("category", "effigy"),
        "type": str(marker.get("label", "Effigy")).removesuffix(" Effigy") if marker.get("category") == "effigy" else "Notes",
        "map": map_id,
        "mapName": map_data["name"],
        "left": round(left, 5),
        "top": round(top, 5),
        "x": map_x,
        "y": map_y,
        "collected": key in collected,
    }


def tracker_payload(selected_player: str = "") -> dict:
    try:
        marker_data = json.loads(MARKERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"ok": False, "error": "Effigy map data is unavailable"}
    markers = [m for m in marker_data.get("markers", []) if m.get("category") in {"effigy", "note"}]
    files = _player_files()
    players_dir = files[0].parent if files else (PERSISTED_PLAYERS if PERSISTED_PLAYERS.exists() else WORK / "Players")
    labels = _player_labels(players_dir)
    players = []
    progress = {}
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            record = _record_data(payload)
            flags = _record_keys(record.get("RelicObtainForInstanceFlag"))
            flags.update(_record_keys(record.get("RelicObtainForInstanceFlagByType")))
            progress[path.stem] = {
                "effigy": flags,
                "note": _record_keys(record.get("NoteObtainForInstanceFlag")),
            }
            player_id = path.stem.lower()
            players.append({"id": path.stem, "label": _display_player_label(player_id, labels)})
        except (OSError, json.JSONDecodeError):
            continue
    default_player = next((player["id"] for player in players if player["label"].lower() == "david"), players[0]["id"] if players else "")
    chosen = selected_player if selected_player in progress else default_player
    collected = progress.get(chosen, {"effigy": set(), "note": set()})
    result = [_marker_payload(marker, collected.get(marker.get("category"), set())) for marker in markers]
    effigy_markers = [marker for marker in result if marker["category"] == "effigy"]
    note_markers = [marker for marker in result if marker["category"] == "note"]
    return {
        "ok": True,
        "players": players,
        "selectedPlayer": chosen,
        "maps": {key: {"name": value["name"], "image": value["image"]} for key, value in MAPS.items()},
        "markers": result,
        "collected": sum(1 for marker in effigy_markers if marker["collected"]),
        "total": len(effigy_markers),
        "effigyCollected": sum(1 for marker in effigy_markers if marker["collected"]),
        "effigyTotal": len(effigy_markers),
        "noteCollected": sum(1 for marker in note_markers if marker["collected"]),
        "noteTotal": len(note_markers),
        "loaded": bool(chosen),
        "source": "synced save" if chosen else "no decoded player save",
    }
