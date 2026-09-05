"""Shared Palworld data loading and metadata helpers."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path

try:
    from django.conf import settings
except ImportError:
    settings = None

ROOT = Path(settings.BASE_DIR) if settings is not None and settings.configured else Path(__file__).resolve().parents[3]
LOCAL_ROOT = Path(os.environ.get("PALWORLD_LOCAL_ROOT", ROOT / "local" / "pals"))
DATA_ROOT = LOCAL_ROOT / "data"
REPORTS_ROOT = LOCAL_ROOT / "reports"
ROSTER = DATA_ROOT / "pal_roster.csv"
PASSIVE_INVENTORY = DATA_ROOT / "passive_inventory.csv"
BREEDING = DATA_ROOT / "breeding" / "pals.json"
WORK_OVERRIDES = DATA_ROOT / "work_suitability_overrides.json"
PALPEDIA_WORK = DATA_ROOT / "palpedia_work_suitability.json"
ANALYZER = Path(__file__).with_name("analyze_pal_breeding.py")
UPLOADS = LOCAL_ROOT / "uploads"
WORK = Path(os.environ.get("PALWORLD_DECODE_WORK_DIR", LOCAL_ROOT / "decode-work"))
TOOLS = Path(os.environ.get("PALWORLD_PARSER_TOOLS_DIR", Path.home() / "AppData" / "Local" / "Temp" / "palworld_parser_tools"))
LIVE_SAVE_ENV = os.environ.get("PALWORLD_LIVE_SAVE_DIR", "").strip()
LIVE_SAVE_DIR = Path(LIVE_SAVE_ENV) if LIVE_SAVE_ENV else None
LIVE_LOCK = threading.Lock()
LIVE_STATE_FILE = DATA_ROOT / "live_save_state.json"
BASE_LABELS_FILE = DATA_ROOT / "base_labels.json"
IMPLANT_INVENTORY_FILE = DATA_ROOT / "implant_inventory.json"
PASSIVE_COLOR_OVERRIDES_FILE = DATA_ROOT / "passive_color_overrides.json"
LIVE_STATE = {
    "last_refresh_fingerprint": "",
    "last_refresh_at": "",
    "last_result": None,
}
if LIVE_STATE_FILE.exists():
    try:
        LIVE_STATE.update(json.loads(LIVE_STATE_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        pass
PAL_IMAGES = TOOLS / "palworld-server-tool" / "web" / "src" / "assets" / "pals"
LOCAL_PAL_IMAGES = LOCAL_ROOT / "assets" / "pals"
SKILL_METADATA = TOOLS / "palworld-server-tool" / "web" / "src" / "assets" / "skill.json"
TARGET_ONLY = "target_only"
LEAST_JUNK = "least_junk"
GOLD_PASSIVES = {
    "Artisan",
    "Burly Body",
    "Demon God",
    "Diet Lover",
    "Earth Emperor",
    "Eternal Flame",
    "Farmhand",
    "Ferocious",
    "Flame Emperor",
    "Ice Emperor",
    "Lord of Lightning",
    "Lord of the Sea",
    "Logging Foreman",
    "Mine Foreman",
    "Mining Foreman",
    "Musclehead",
    "Otherworldly Cells",
    "Philanthropist",
    "Serenity",
    "Service-Minded",
    "Spirit Emperor",
    "Vampiric",
    "Workaholic",
}

NEGATIVE_PASSIVES = {
    "Bottomless Stomach",
    "Brittle",
    "Clumsy",
    "Coward",
    "Destructive",
    "Downtrodden",
    "Glutton",
    "Mercy Hit",
    "Pacifist",
    "Slacker",
    "Unstable",
}

BLUE_PASSIVES = {
    "Ancient Might",
    "Diamond Body",
    "Demon's Hand",
    "Demon’s Hand",
    "Dimensional Leap",
    "Eternal Engine",
    "Eternal Engine S",
    "Infinite Stamina",
    "Invader",
    "Lavish Hospitality",
    "Legend",
    "Babysitter",
    "Heavily Armored",
    "Idiosyncratic",
    "Immortality",
    "Remarkable Craftsmanship",
    "Ranch Master",
    "Skymarcher",
    "Lucky",
    "Runner",
    "Swift",
}

NORMAL_PASSIVES = {
    "Conceited",
    "Fit as a Fiddle",
    "Impatient",
    "Insomnia",
    "Nimble",
    "Work Slave",
}

WORK_LABELS = {
    "kindling": "Kindling",
    "watering": "Watering",
    "planting": "Planting",
    "electric": "Electricity",
    "handiwork": "Handiwork",
    "gathering": "Gathering",
    "mining": "Mining",
    "farming": "Farming",
    "lumbering": "Lumbering",
    "medicine": "Medicine",
    "cooling": "Cooling",
    "transporting": "Transporting",
}

SIZE_ORDER = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4, "Unknown": 5}
POPULAR_WORK_PICKS = {"handiwork": "Anubis", "mining": "Anubis"}

WORK_SITE_PATTERNS = [
    ("BreedFarm", []),
    ("HatchingPalEgg", []),
    ("FarmBlock", ["planting", "watering", "gathering"]),
    ("MonsterFarm", ["farming"]),
    ("StonePit", ["mining"]),
    ("CoalPit", ["mining"]),
    ("CopperPit", ["mining"]),
    ("QuartzPit", ["mining"]),
    ("CrystalPit", ["mining"]),
    ("OilPump", ["mining"]),
    ("StationDeforest", ["lumbering"]),
    ("ElectricGenerator", ["electric"]),
    ("Cooler", ["cooling"]),
    ("Refrigerator", ["cooling"]),
    ("CampFire", ["kindling"]),
    ("CookingStove", ["kindling"]),
    ("HugeKitchen", ["kindling"]),
    ("BlastFurnace", ["kindling"]),
    ("Furnace", ["kindling"]),
    ("FlourMill", ["watering"]),
    ("MedicineFacility", ["medicine"]),
    ("Clinic", ["medicine"]),
    ("Workbench", ["handiwork"]),
    ("WorkBench", ["handiwork"]),
    ("Factory", ["handiwork"]),
    ("SphereFactory", ["handiwork"]),
    ("WeaponFactory", ["handiwork"]),
    ("CompositeDesk", ["handiwork"]),
]

AUTO_TARGET_CAPS = {
    "kindling": 2,
    "watering": 2,
    "planting": 3,
    "electric": 2,
    "handiwork": 3,
    "gathering": 3,
    "mining": 5,
    "farming": 3,
    "lumbering": 3,
    "medicine": 1,
    "cooling": 1,
    "transporting": 5,
}

SIZE_GROUPS = {
    "XS": "Extra Small",
    "S": "Small",
    "M": "Medium",
    "L": "Large",
    "XL": "Extra Large",
    "Unknown": "Unknown Size",
}

VALID_PAL_SIZES = {"XS", "S", "M", "L", "XL"}
PASSIVE_TONES = {"positive", "gold", "negative", "neutral"}


def as_int(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_species(name: str) -> str:
    name = (name or "").strip()
    if name.startswith("BOSS_"):
        name = name[5:]
    return name.replace("(BOSS)", "").strip()


def split_passives(value: str | None) -> frozenset[str]:
    return frozenset(p.strip() for p in (value or "").split(";") if p.strip())


def match_key(value: str) -> str:
    return re.sub(r"[\s_-]+", " ", (value or "").strip().lower())


def canonical_passives(values: list[str]) -> frozenset[str]:
    by_key = {match_key(passive): passive for passive in STORE.passives}
    return frozenset(by_key.get(match_key(p), p.strip()) for p in values if p and p.strip())


def load_passive_color_overrides() -> dict[str, str]:
    if not PASSIVE_COLOR_OVERRIDES_FILE.exists():
        return {}
    try:
        data = json.loads(PASSIVE_COLOR_OVERRIDES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(passive): str(tone)
        for passive, tone in data.items()
        if str(passive).strip() and str(tone) in PASSIVE_TONES
    }


def save_passive_color_overrides(overrides: dict[str, str]) -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    cleaned = {
        str(passive): str(tone)
        for passive, tone in sorted(overrides.items())
        if str(passive).strip() and str(tone) in PASSIVE_TONES
    }
    PASSIVE_COLOR_OVERRIDES_FILE.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")


def passive_tone(name: str, passive_id: str = "", desc: str = "") -> str:
    lowered = f"{passive_id} {desc}".lower()
    pid = passive_id or ""
    if name in NORMAL_PASSIVES or pid in {"PAL_conceited", "CraftSpeed_up1"}:
        return "neutral"
    if re.match(r"ElementBoost_[A-Za-z]+_2_PAL$", pid):
        return "gold"
    if re.match(r"ElementBoost_[A-Za-z]+_1_PAL$", pid):
        return "positive"
    if name in BLUE_PASSIVES or pid.startswith("MutationPal_") or pid == "CraftSpeed_up3" or pid.startswith("RideJumpCount_Increase"):
        return "positive"
    if name in NEGATIVE_PASSIVES or pid.endswith("_down1") or pid.endswith("_down2") or pid.endswith("_down3"):
        return "negative"
    if name in GOLD_PASSIVES:
        return "gold"
    positive_terms = ("+", " up", "increase", "immune", "work suitability")
    has_positive = any(term in lowered for term in positive_terms)
    has_negative = " -" in lowered or "down" in lowered or "decrease" in lowered
    if has_negative and not has_positive:
        return "negative"
    if pid.endswith("_up2") or "work suitability +1" in lowered:
        return "gold"
    if name in BLUE_PASSIVES:
        return "positive"
    return "neutral"


def passive_metadata_by_name() -> dict[str, dict[str, str]]:
    if not SKILL_METADATA.exists():
        return {}
    try:
        skill_data = json.loads(SKILL_METADATA.read_text(encoding="utf-8")).get("en", {})
    except (OSError, json.JSONDecodeError):
        return {}
    by_name = {}
    for passive_id, skill in skill_data.items():
        if not isinstance(skill, dict):
            continue
        name = str(skill.get("name") or "").strip()
        if not name:
            continue
        by_name[name] = {
            "id": str(passive_id),
            "desc": str(skill.get("desc") or ""),
            "tone": passive_tone(name, str(passive_id), str(skill.get("desc") or "")),
        }
    return by_name


def build_passive_meta(passives: list[str]) -> dict[str, dict[str, str]]:
    by_name = passive_metadata_by_name()
    if PASSIVE_INVENTORY.exists():
        with PASSIVE_INVENTORY.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = row.get("passive_name", "")
                passive_id = row.get("passive_id", "")
                skill = by_name.get(name, {})
                by_name[name] = {
                    "id": passive_id,
                    "desc": skill.get("desc", ""),
                    "tone": passive_tone(name, passive_id, skill.get("desc", "")),
                }

    overrides = load_passive_color_overrides()
    meta = {}
    for passive in passives:
        entry = dict(by_name.get(passive, {"id": "", "desc": "", "tone": passive_tone(passive)}))
        if passive in overrides:
            entry["tone"] = overrides[passive]
            entry["toneSource"] = "override"
        else:
            entry["toneSource"] = "default"
        meta[passive] = entry
    return meta


def palbox_position(location: str) -> dict[str, int | None]:
    if not (location or "").lower().startswith("palbox/storage"):
        return {"rawSlot": None, "box": None, "slot": None}
    match = re.search(r"slot\s+(\d+)", location or "", re.I)
    if not match:
        return {"rawSlot": None, "box": None, "slot": None}
    raw = int(match.group(1))
    return {"rawSlot": raw, "box": raw // 30 + 1, "slot": raw % 30 + 1}


def base_slot(location: str) -> int | None:
    if not re.match(r"^\s*Base\b", location or "", re.I):
        return None
    match = re.search(r"\bslot\s+(\d+)\b", location or "", re.I)
    return as_int(match.group(1)) + 1 if match else None


@dataclass(frozen=True)
class BreedPal:
    key: str
    name: str
    rank: int
    priority: int
    breedable: bool
    unique_only: bool


class DataStore:
    def __init__(self):
        self.reload()

    def reload(self):
        if BREEDING.exists():
            self.breeding_data = json.loads(BREEDING.read_text(encoding="utf-8"))
        else:
            self.breeding_data = {"pals": [], "uniqueCombos": [], "dataVersion": "missing local data", "generatedAt": ""}
        self.pals = {
            p["key"]: BreedPal(
                key=p["key"],
                name=p["name"],
                rank=as_int(p.get("combiRank")),
                priority=as_int(p.get("combiPriority")),
                breedable=bool(p.get("breedable", True)),
                unique_only=bool(p.get("uniqueOnly", False)),
            )
            for p in self.breeding_data["pals"]
        }
        self.name_to_key = {p.name.lower(): p.key for p in self.pals.values()}
        self.unique = {tuple(sorted(c["parents"][:2])): c["child"] for c in self.breeding_data.get("uniqueCombos", [])}
        self.generic_pool = [p for p in self.pals.values() if p.breedable and not p.unique_only]
        self.generic_pool.sort(key=lambda p: (p.rank, p.priority))
        self.child_cache: dict[tuple[str, str], str | None] = {}
        self.parent_pair_cache: dict[str, list[tuple[str, str]]] = {}
        if ROSTER.exists():
            with ROSTER.open(newline="", encoding="utf-8-sig") as f:
                self.roster = list(csv.DictReader(f))
        else:
            self.roster = []
        self.species_names = sorted({p.name for p in self.pals.values()})
        metadata_passives = set(passive_metadata_by_name())
        roster_passives = {p for r in self.roster for p in split_passives(r.get("passives"))}
        self.passives = sorted(metadata_passives | roster_passives)
        self.passive_meta = build_passive_meta(self.passives)
        self.passives_by_owner = {}
        for row in self.roster:
            owner = row.get("owner", "")
            if not owner:
                continue
            self.passives_by_owner.setdefault(owner, set()).update(split_passives(row.get("passives")))
        self.passives_by_owner = {owner: sorted(values) for owner, values in self.passives_by_owner.items()}
        self.owners = sorted({r.get("owner", "") for r in self.roster if r.get("owner")})
        self.palpedia_work_source = {}
        self.palpedia_work = {}
        if PALPEDIA_WORK.exists():
            try:
                self.palpedia_work_source = json.loads(PALPEDIA_WORK.read_text(encoding="utf-8"))
                entries = self.palpedia_work_source.get("entries") or {}
                self.palpedia_work = {match_key(name): entry for name, entry in entries.items() if isinstance(entry, dict)}
            except (OSError, json.JSONDecodeError):
                self.palpedia_work_source = {}
                self.palpedia_work = {}

    def child_for(self, a: str, b: str) -> str | None:
        pair = tuple(sorted((a, b)))
        if pair in self.child_cache:
            return self.child_cache[pair]
        if a not in self.pals or b not in self.pals:
            self.child_cache[pair] = None
            return None
        pa, pb = self.pals[a], self.pals[b]
        if not pa.breedable or not pb.breedable:
            self.child_cache[pair] = None
            return None
        if a == b:
            self.child_cache[pair] = a
            return a
        if pair in self.unique:
            self.child_cache[pair] = self.unique[pair]
            return self.child_cache[pair]
        target_rank = math.floor((pa.rank + pb.rank + 1) / 2)
        best = min(self.generic_pool, key=lambda p: (abs(p.rank - target_rank), -p.priority))
        self.child_cache[pair] = best.key
        return best.key

    def parent_pairs_for_child(self, child_key: str) -> list[tuple[str, str]]:
        if child_key in self.parent_pair_cache:
            return self.parent_pair_cache[child_key]
        keys = [key for key, pal in self.pals.items() if pal.breedable]
        pairs: list[tuple[str, str]] = []
        for idx, a in enumerate(keys):
            for b in keys[idx:]:
                if self.child_for(a, b) == child_key:
                    pairs.append((a, b))
        self.parent_pair_cache[child_key] = pairs
        return pairs


STORE = DataStore()


def module_status() -> dict[str, str]:
    return {
        "state": "ready",
        "message": f"Loaded {len(STORE.roster)} Pals across {len(STORE.owners)} owners.",
    }
