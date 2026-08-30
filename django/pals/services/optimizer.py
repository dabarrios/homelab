from __future__ import annotations

import csv
import os
import json
import math
import re
import shutil
import subprocess
import threading
import zipfile
from datetime import datetime
from dataclasses import dataclass, replace
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from itertools import combinations, product
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

try:
    from django.conf import settings
except ImportError:
    settings = None

ROOT = Path(settings.BASE_DIR) if settings is not None and settings.configured else Path(__file__).resolve().parents[3]
LOCAL_ROOT = Path(os.environ.get("PALWORLD_LOCAL_ROOT", ROOT / "local" / "pals"))
DATA_ROOT = LOCAL_ROOT / "data"
REPORTS_ROOT = LOCAL_ROOT / "reports"
WEB = ROOT / "web"
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
def as_int(value, default=0):
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


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

def passive_tone(name: str, passive_id: str = "", desc: str = "") -> str:
    lowered = f"{passive_id} {desc}".lower()
    pid = passive_id or ""
    if name in NORMAL_PASSIVES or pid in {"PAL_conceited", "CraftSpeed_up1"}:
        return "neutral"
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

def build_passive_meta(passives: list[str]) -> dict[str, dict[str, str]]:
    by_id: dict[str, dict[str, str]] = {}
    if SKILL_METADATA.exists():
        skill_data = json.loads(SKILL_METADATA.read_text(encoding="utf-8")).get("en", {})
        by_id = {key: value for key, value in skill_data.items() if isinstance(value, dict)}

    by_name: dict[str, dict[str, str]] = {}
    if PASSIVE_INVENTORY.exists():
        with PASSIVE_INVENTORY.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = row.get("passive_name", "")
                passive_id = row.get("passive_id", "")
                skill = by_id.get(passive_id, {})
                by_name[name] = {
                    "id": passive_id,
                    "desc": skill.get("desc", ""),
                    "tone": passive_tone(name, passive_id, skill.get("desc", "")),
                }

    return {
        passive: by_name.get(passive, {"id": "", "desc": "", "tone": passive_tone(passive)})
        for passive in passives
    }

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


@dataclass(frozen=True)
class State:
    species_key: str
    species: str
    passives: frozenset[str]
    gender: str
    steps: int
    breed_count: int
    hp_iv: int
    attack_iv: int
    defense_iv: int
    iv_total: int
    iv_sources: int
    label: str
    location: str
    box: int | None
    slot: int | None
    base_slot: int | None = None
    base_workers_used: int = 0
    instance_id: str = ""
    parents: tuple["State", "State"] | None = None

    @property
    def id(self) -> str:
        return f"{self.species_key}|{','.join(sorted(self.passives))}|{self.gender}|{self.steps}|{self.breed_count}|{self.label}"

    @property
    def avg_iv(self) -> float:
        return self.iv_total / max(1, self.iv_sources)

    @property
    def avg_hp_iv(self) -> float:
        return self.hp_iv / max(1, self.iv_sources)

    @property
    def avg_attack_iv(self) -> float:
        return self.attack_iv / max(1, self.iv_sources)

    @property
    def avg_defense_iv(self) -> float:
        return self.defense_iv / max(1, self.iv_sources)


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
        self.passives = sorted({p for r in self.roster for p in split_passives(r.get("passives"))})
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



def pal_image_path(name: str) -> Path | None:
    safe_name = Path(name).name
    for root in (LOCAL_PAL_IMAGES, PAL_IMAGES):
        try:
            file_path = (root / safe_name).resolve()
            root_path = root.resolve()
        except OSError:
            continue
        if str(file_path).startswith(str(root_path)) and file_path.exists():
            return file_path
    return None


def icon_url_for_key(key: str) -> str | None:
    for suffix in (".png", ".webp"):
        name = f"{key}{suffix}"
        if pal_image_path(name):
            return f"/assets/pals/{name}"
    return None


def species_meta() -> dict[str, dict]:
    return {
        pal.get("name", ""): {
            "key": pal.get("key", ""),
            "types": pal.get("types", []),
            "icon": icon_url_for_key(pal.get("key", "")),
        }
        for pal in STORE.breeding_data.get("pals", [])
        if pal.get("name")
    }


def species_types_for_key(key: str) -> list[str]:
    for pal in STORE.breeding_data.get("pals", []):
        if pal.get("key") == key:
            return pal.get("types", [])
    return []


WORK_ORDER_INDEX = {key: idx for idx, key in enumerate(WORK_LABELS)}


def ordered_work_keys(work: dict) -> list[str]:
    return [key for key in WORK_LABELS if as_int(work.get(key)) > 0]


def condensation_rank_targets(work: dict) -> list[str]:
    keys = ordered_work_keys(work)
    if not keys:
        return []
    ranked = sorted(keys, key=lambda key: (-as_int(work.get(key)), WORK_ORDER_INDEX[key]))
    return [ranked[idx % len(ranked)] for idx in range(3)]


def load_work_overrides() -> dict[str, dict]:
    if not WORK_OVERRIDES.exists():
        return {}
    try:
        data = json.loads(WORK_OVERRIDES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {match_key(name): value for name, value in (data.get("overrides") or {}).items()}


WORK_SUITABILITY_OVERRIDES = load_work_overrides()


def work_override_for(name: str) -> dict | None:
    override = WORK_SUITABILITY_OVERRIDES.get(match_key(name))
    if isinstance(override, dict):
        return override
    return None


def palpedia_entry_for(name: str) -> dict | None:
    entry = getattr(STORE, "palpedia_work", {}).get(match_key(name))
    if isinstance(entry, dict):
        return entry
    return None


def work_for_pal(pal: dict) -> dict:
    entry = palpedia_entry_for(pal.get("name", ""))
    if entry:
        return entry.get("baseWork") or {}
    return pal.get("work") or {}


def work_source_for(name: str) -> dict | None:
    entry = palpedia_entry_for(name)
    if entry:
        source = getattr(STORE, "palpedia_work_source", {}) or {}
        fetched = source.get("fetchedAt", "")
        detail = source.get("source", "Palpedia.net Work Suitability")
        if fetched:
            detail = f"{detail}, fetched {fetched}"
        return {"source": detail, "url": source.get("sourceUrl", "")}
    return work_override_for(name)


def projected_fully_condensed_work_levels(work: dict) -> dict[str, int]:
    levels = {key: as_int(work.get(key)) for key in ordered_work_keys(work)}
    for key in condensation_rank_targets(work):
        levels[key] = min(10, levels[key] + 1)
    for key in list(levels):
        levels[key] = min(10, levels[key] + 1)
    return levels


def fully_condensed_work_levels(work: dict, name: str = "") -> dict[str, int]:
    entry = palpedia_entry_for(name)
    if entry:
        verified = entry.get("fullyCondensedWork") or {}
        return {key: as_int(verified.get(key)) for key in WORK_LABELS if as_int(verified.get(key)) > 0}
    override = work_override_for(name)
    if not override:
        return {}
    verified = override.get("fullyCondensedWork") or {}
    return {key: as_int(verified.get(key)) for key in WORK_LABELS if as_int(verified.get(key)) > 0}


def pal_size_for(name: str) -> str:
    entry = palpedia_entry_for(name)
    size = str((entry or {}).get("size") or "").strip().upper()
    if size in VALID_PAL_SIZES:
        return size
    return "Unknown"


def owned_species_counts(owner: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in STORE.roster:
        if owner and row.get("owner") != owner:
            continue
        species = normalize_species(row.get("species", ""))
        if not species:
            continue
        counts[species] = counts.get(species, 0) + 1
    return counts


def work_entries(work: dict, name: str = "") -> list[dict]:
    entries = []
    condensed_levels = fully_condensed_work_levels(work, name)
    projected_levels = projected_fully_condensed_work_levels(work)
    for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1]):
        level = as_int(work.get(key))
        if level <= 0:
            continue
        entries.append({
            "key": key,
            "label": label,
            "level": level,
            "fullyCondensedLevel": condensed_levels.get(key),
            "projectedFullyCondensedLevel": projected_levels.get(key),
        })
    return entries


def card_final_level(card: dict) -> int:
    return as_int(card.get("selectedFullyCondensedLevel") or card.get("selectedLevel"))


def requires_owned_seed_for_breeding(species_key: str) -> bool:
    pairs = STORE.parent_pairs_for_child(species_key)
    return bool(pairs) and all(a == species_key and b == species_key for a, b in pairs)


def work_recommendations(cards: list[dict], selected_work: str, include_self_breeders: bool = True) -> list[dict]:
    if not cards:
        return []
    pick_pool = cards if include_self_breeders else [card for card in cards if not card.get("requiresOwnedSeed")]
    pick_pool = pick_pool or cards

    def best(sort_key):
        return sorted(pick_pool, key=sort_key)[0]

    popular_name = POPULAR_WORK_PICKS.get(selected_work)
    popular = next((card for card in pick_pool if card.get("name") == popular_name), None) if popular_name else None
    practical = popular or best(lambda card: (
        -card_final_level(card),
        0 if card.get("size") in {"S", "M"} else 1 if card.get("size") in {"XS", "L"} else 2,
        card.get("workCount", 99),
        0 if card.get("ownedCount") else 1,
        card.get("name", ""),
    ))
    def best_for_sizes(sizes: set[str]) -> dict | None:
        pool = [card for card in pick_pool if card.get("size") in sizes]
        return sorted(pool, key=lambda card: (
            -card_final_level(card),
            -as_int(card.get("selectedLevel")),
            card.get("workCount", 99),
            0 if card.get("ownedCount") else 1,
            SIZE_ORDER.get(card.get("size"), 99),
            card.get("name", ""),
        ))[0] if pool else None
    dark_pool = [card for card in pick_pool if any("dark" == str(type_name).lower() for type_name in card.get("types", []))]

    specs = [
        ("recommended", "Recommended", "Common practical choice for this work skill." if popular else "Best practical mix of final level, footprint, focus, and ownership.", practical),
        ("dark", "Best Dark", "Best dark-type option for this work skill; dark Pals do not need Insomnia for night uptime.", sorted(dark_pool, key=lambda card: (
            -card_final_level(card),
            -as_int(card.get("selectedLevel")),
            0 if card.get("size") in {"S", "M"} else 1 if card.get("size") in {"XS", "L"} else 2,
            card.get("workCount", 99),
            0 if card.get("ownedCount") else 1,
            card.get("name", ""),
        ))[0] if dark_pool else None),
        ("xl", "Best XL", "Highest selected work level among XL Pals.", best_for_sizes({"XL"})),
        ("large", "Best L", "Highest selected work level among L Pals.", best_for_sizes({"L"})),
        ("medium", "Best Medium", "Highest selected work level among Medium (M) Pals.", best_for_sizes({"M"})),
        ("small", "Best Small", "Highest selected work level among Small (S) Pals.", best_for_sizes({"S"})),
        ("xs", "Best XS", "Highest selected work level among Extra Small (XS) Pals.", best_for_sizes({"XS"})),
    ]
    seen = set()
    recommendations = []
    for role, title, reason, card in specs:
        if not card:
            continue
        recommendations.append({
            "role": role,
            "title": title,
            "reason": reason,
            "card": card,
            "duplicate": card.get("name") in seen,
        })
        seen.add(card.get("name"))
    return recommendations


def work_suitability_payload(owner: str = "", selected_work: str = "", include_self_breeders: bool = True) -> dict:
    if selected_work not in WORK_LABELS:
        return {
            "error": "Choose a work skill.",
            "groups": [],
            "recommendations": [],
            "selectedWork": "",
            "selectedWorkLabel": "",
            "total": 0,
            "verifiedCondensationCount": 0,
        }
    counts = owned_species_counts(owner)
    cards = []
    for pal in STORE.breeding_data.get("pals", []):
        work = work_for_pal(pal)
        level = as_int(work.get(selected_work))
        if level <= 0:
            continue
        name = pal.get("name", "")
        size = pal_size_for(name)
        entries = work_entries(work, name)
        condensed_levels = fully_condensed_work_levels(work, name)
        projected_levels = projected_fully_condensed_work_levels(work)
        work_source = work_source_for(name)
        requires_seed = requires_owned_seed_for_breeding(pal.get("key", ""))
        owned_count = counts.get(name, 0)
        cards.append({
            "key": pal.get("key", ""),
            "name": name,
            "types": pal.get("types", []),
            "icon": icon_url_for_key(pal.get("key", "")),
            "size": size,
            "sizeGroup": SIZE_GROUPS.get(size, "Unknown Size"),
            "sizeKnown": size != "Unknown",
            "selectedWork": selected_work,
            "selectedWorkLabel": WORK_LABELS[selected_work],
            "selectedLevel": level,
            "selectedFullyCondensedLevel": condensed_levels.get(selected_work),
            "selectedProjectedFullyCondensedLevel": projected_levels.get(selected_work),
            "work": entries,
            "workCount": len(entries),
            "workCondensationSource": "verified" if work_source else "projected",
            "workCondensationSourceDetail": (work_source or {}).get("source", ""),
            "workCondensationSourceUrl": (work_source or {}).get("url", ""),
            "ownedCount": owned_count,
            "breedable": bool(pal.get("breedable", True)),
            "uniqueOnly": bool(pal.get("uniqueOnly", False)),
            "requiresOwnedSeed": requires_seed,
            "unavailableReason": f"It looks like you need to tame or capture {name} first. Once you own one, come back and self-breed it." if requires_seed and not owned_count else "",
        })
    if not include_self_breeders:
        cards = [card for card in cards if not card["requiresOwnedSeed"]]
    cards.sort(key=lambda item: (
        SIZE_ORDER.get(item["size"], 99),
        -card_final_level(item),
        -as_int(item.get("selectedLevel")),
        item["workCount"],
        0 if item.get("ownedCount") else 1,
        item["name"],
    ))
    grouped: dict[str, list[dict]] = {}
    for card in cards:
        grouped.setdefault(card["sizeGroup"], []).append(card)
    group_order = ["Extra Small", "Small", "Medium", "Large", "Extra Large", "Unknown Size"]
    groups = [
        {"title": title, "cards": grouped.get(title, [])}
        for title in group_order
        if grouped.get(title)
    ]
    return {
        "workTypes": [{"key": key, "label": label} for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1])],
        "selectedWork": selected_work,
        "selectedWorkLabel": WORK_LABELS[selected_work],
        "owner": owner,
        "groups": groups,
        "recommendations": work_recommendations(cards, selected_work, include_self_breeders=include_self_breeders),
        "includeSelfBreeders": include_self_breeders,
        "total": len(cards),
        "knownSizeCount": sum(1 for card in cards if card["sizeKnown"]),
        "verifiedCondensationCount": sum(1 for card in cards if card["workCondensationSource"] == "verified"),
        "condensationNote": "Work Suitability uses Palpedia.net base and condenser-star data when available. Missing species fall back to bundled base work levels and are marked Needs verification.",
        "sizeSourceNote": "Size uses Palpedia species metadata. Unknown size means the species was missing or had no recognized size in the synced Palpedia data.",
    }


def normalized_item_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def ranch_drop_names_for_pal(pal: dict) -> set[str]:
    work = work_for_pal(pal)
    if as_int(work.get("farming")) <= 0:
        return set()
    partner = pal.get("partnerSkill") or {}
    desc = str(partner.get("desc") or "")
    desc_key = normalized_item_text(desc)
    desc_lower = desc.lower()
    if "ranch" not in desc_lower:
        return set()
    drops = [drop for drop in (pal.get("drops") or []) if isinstance(drop, dict) and drop.get("name")]
    names = {drop.get("name", "") for drop in drops}
    found = {name for name in names if normalized_item_text(name) and normalized_item_text(name) in desc_key}
    if "variousseeds" in desc_key:
        found.update(name for name in names if "seed" in name.lower())
    if "mushroomorcavernmushroom" in desc_key:
        found.update(name for name in names if "mushroom" in name.lower())
    if "laysanegg" in desc_key:
        found.update(name for name in names if normalized_item_text(name) == "egg")
    if "itemsfromtheground" in desc_key:
        found.update(names)
    return found


def ranch_drops_payload(owner: str = "", include_self_breeders: bool = True) -> dict:
    counts = owned_species_counts(owner)
    items: dict[str, dict] = {}
    pal_count = 0
    for pal in STORE.breeding_data.get("pals", []):
        ranch_names = ranch_drop_names_for_pal(pal)
        if not ranch_names:
            continue
        pal_count += 1
        card = work_card_for_pal(pal, counts, "farming")
        partner = pal.get("partnerSkill") or {}
        card["ranchDrops"] = [
            drop for drop in (pal.get("drops") or [])
            if isinstance(drop, dict) and drop.get("name") in ranch_names
        ]
        card["partnerSkill"] = {
            "name": partner.get("name", ""),
            "desc": partner.get("desc", ""),
        }
        for drop in card["ranchDrops"]:
            name = drop.get("name", "")
            if not name:
                continue
            bucket = items.setdefault(name, {"name": name, "pals": []})
            bucket["pals"].append(card)

    def pal_sort_key(card: dict):
        return (
            0 if card.get("ownedCount") else 1,
            -as_int(card.get("selectedFullyCondensedLevel") or card.get("selectedLevel")),
            0 if card.get("size") in {"S", "M"} else 1 if card.get("size") in {"XS", "L"} else 2,
            card.get("workCount", 99),
            card.get("name", ""),
        )

    results = []
    for item in items.values():
        pals = sorted(item["pals"], key=pal_sort_key)
        pick_pool = pals if include_self_breeders else [card for card in pals if not card.get("requiresOwnedSeed")]
        pick_pool = pick_pool or pals
        results.append({
            "name": item["name"],
            "count": len(pals),
            "best": pick_pool[0] if pick_pool else None,
            "pals": pals,
        })
    results.sort(key=lambda item: item["name"])
    return {
        "owner": owner,
        "items": results,
        "includeSelfBreeders": include_self_breeders,
        "totalItems": len(results),
        "totalPals": pal_count,
        "sourceNote": "Ranch Drops uses Pals with Farming suitability and partner-skill text that mentions assignment to a Ranch. Item names are matched from the Pal's bundled drops only when the ranch text names or implies that item.",
    }


BASE_WORK_CACHE = {"mtime": None, "payload": None}


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


def guid_text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "value" in value:
            return guid_text(value.get("value"))
        parts = [value.get(k) for k in ("a", "b", "c", "d") if value.get(k) is not None]
        if parts:
            return "-".join(str(p) for p in parts)
    return str(value or "")


def save_to_map_coords(loc: dict) -> dict[str, float]:
    data_x = float(loc.get("x", 0) or 0)
    data_y = float(loc.get("y", 0) or 0)
    return {
        "x": round((data_y - 158000) / 459, 1),
        "y": round((data_x + 123888) / 459, 1),
        "z": round(float(loc.get("z", 0) or 0) / 100, 1),
    }


def base_coord_text(loc: dict) -> str:
    coords = save_to_map_coords(loc)
    return f"{coords['x']:.0f}, {coords['y']:.0f}"


def infer_work_site_skills(name: str) -> list[str]:
    raw = name or ""
    for pattern, skills in WORK_SITE_PATTERNS:
        if pattern.lower() in raw.lower():
            return list(skills)
    return []


def readable_site_name(value: str) -> str:
    name = re.sub(r"_\d+$", "", value or "Unknown")
    replacements = {
        "FarmBlockV2_wheet": "Wheat Plantation",
        "FarmBlockV2_Berries": "Berry Plantation",
        "FarmBlockV2_Carrot": "Carrot Plantation",
        "FarmBlockV2_Lettuce": "Lettuce Plantation",
        "FarmBlockV2_tomato": "Tomato Plantation",
        "FarmBlockV2_Onion": "Onion Plantation",
        "FarmBlockV2_Potato": "Potato Plantation",
        "BreedFarm": "Breeding Farm",
        "HatchingPalEgg": "Egg Incubator",
        "MonsterFarm": "Ranch",
        "StationDeforest2": "Logging Site",
        "StationDeforest3": "Logging Site",
        "StonePit": "Stone Pit",
        "CoalPit": "Coal Mine",
        "CopperPit_2": "Ore Mining Site II",
        "CopperPit": "Ore Mining Site",
        "QuartzPit": "Pure Quartz Mine",
        "CrystalPit": "Sulfur Mine",
        "OilPump": "Crude Oil Extractor",
        "ElectricGenerator": "Power Generator",
        "HugeKitchen": "Electric Kitchen",
        "CookingStove": "Cooking Pot",
        "CampFire": "Campfire",
        "Refrigerator": "Refrigerator",
        "Cooler": "Cooler",
        "BlastFurnace": "Furnace",
        "FlourMill": "Mill",
        "Clinic": "Medicine Facility",
        "MedicineFacility_01": "Medicine Workbench",
        "Workbench": "Workbench",
        "WorkBench_SkillUnlock": "Pal Gear Workbench",
        "SphereFactory_Black_03": "Sphere Assembly Line",
        "SphereFactory_Black_01": "Sphere Workbench",
        "WeaponFactory_Dirty_03": "Weapon Assembly Line",
        "WeaponFactory_Dirty_01": "Weapon Workbench",
        "Factory_Hard_03": "Production Assembly Line",
        "Factory_Hard_01": "Production Workbench",
        "CompositeDesk": "Monitoring Stand",
    }
    return replacements.get(name, replacements.get(re.sub(r"_\d+$", "", name), re.sub(r"(?<!^)(?=[A-Z])", " ", name).replace("_", " ").strip()))


def load_level_world_data() -> dict:
    level_json = WORK / "Level.full.json"
    if not level_json.exists():
        return {}
    return json.loads(level_json.read_text(encoding="utf-8")).get("properties", {}).get("worldSaveData", {}).get("value", {})


def base_work_sites_payload() -> dict:
    level_json = WORK / "Level.full.json"
    if not level_json.exists():
        return {"ok": False, "error": "No decoded Level.full.json is available. Sync Save first.", "bases": []}
    mtime = level_json.stat().st_mtime_ns
    labels = load_base_labels()
    cached = BASE_WORK_CACHE.get("payload")
    if cached and BASE_WORK_CACHE.get("mtime") == mtime:
        payload = json.loads(json.dumps(cached))
        for base in payload.get("bases", []):
            label = labels.get(base.get("id"), "")
            base["customName"] = label
            base["displayName"] = label or base.get("defaultName")
        payload["labels"] = labels
        return payload

    ws = load_level_world_data()
    if not ws:
        return {"ok": False, "error": "Decoded Level.full.json did not contain worldSaveData.", "bases": []}

    model_to_obj = {}
    for item in ws.get("MapObjectSaveData", {}).get("value", {}).get("values", []):
        raw = item.get("Model", {}).get("value", {}).get("RawData", {}).get("value", {})
        mid = guid_text(raw.get("instance_id"))
        if mid:
            model_to_obj[mid] = item.get("MapObjectId", {}).get("value", "")

    work_by_id = {}
    for item in ws.get("WorkSaveData", {}).get("value", {}).get("values", []):
        raw = item.get("RawData", {}).get("value", {})
        wid = guid_text(raw.get("id"))
        if wid:
            work_by_id[wid] = raw

    bases = []
    for idx, entry in enumerate(ws.get("BaseCampSaveData", {}).get("value", []), 1):
        base = entry.get("value", {})
        raw = base.get("WorkerDirector", {}).get("value", {}).get("RawData", {}).get("value", {})
        base_id = guid_text(raw.get("id")) or f"base-{idx}"
        loc = raw.get("spawn_transform", {}).get("translation", {}) or {}
        work_ids = base.get("WorkCollection", {}).get("value", {}).get("RawData", {}).get("value", {}).get("work_ids", [])
        sites = []
        demand = {key: 0 for key in WORK_LABELS}
        unresolved = 0
        seen = set()
        for wid_value in work_ids:
            wid = guid_text(wid_value)
            wr = work_by_id.get(wid)
            if not wr:
                unresolved += 1
                continue
            define = wr.get("assign_define_data_id") or ""
            obj = model_to_obj.get(guid_text(wr.get("owner_map_object_model_id")), "")
            site_key = (define, obj, guid_text(wr.get("owner_map_object_model_id")))
            if site_key in seen:
                continue
            seen.add(site_key)
            site_name = obj or define or "Unknown"
            skills = infer_work_site_skills(site_name) or infer_work_site_skills(define)
            for skill in skills:
                if skill in demand:
                    demand[skill] += 1
            sites.append({
                "id": wid,
                "defineId": define,
                "objectId": obj,
                "name": readable_site_name(site_name or define),
                "skills": skills,
                "state": wr.get("current_state"),
                "requiredWork": wr.get("required_work_amount"),
                "currentWork": wr.get("current_work_amount"),
            })
        default_name = f"Base {idx} ({base_coord_text(loc)})"
        custom = labels.get(base_id, "")
        bases.append({
            "id": base_id,
            "index": idx,
            "defaultName": default_name,
            "customName": custom,
            "displayName": custom or default_name,
            "coords": save_to_map_coords(loc),
            "rawCoords": {"x": round(float(loc.get("x", 0) or 0), 1), "y": round(float(loc.get("y", 0) or 0), 1), "z": round(float(loc.get("z", 0) or 0), 1)},
            "siteCount": len(sites),
            "unresolvedWorkIds": unresolved,
            "sites": sorted(sites, key=lambda s: (s.get("name", ""), s.get("defineId", ""))),
            "demand": {key: value for key, value in demand.items() if value > 0},
        })
    payload = {"ok": True, "bases": bases, "labels": labels, "workTypes": [{"key": key, "label": label} for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1])]}
    BASE_WORK_CACHE["mtime"] = mtime
    BASE_WORK_CACHE["payload"] = json.loads(json.dumps(payload))
    return payload


def display_owned_location(location: str) -> str:
    match = re.search(
        r"^Base\s+(\d+)\s+@\s+\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)",
        location or "",
        re.I,
    )
    if not match:
        return location or ""
    base_index = as_int(match.group(1))
    x = float(match.group(2))
    y = float(match.group(3))
    payload = base_work_sites_payload()
    bases = payload.get("bases", []) if payload.get("ok") else []
    base = next((item for item in bases if as_int(item.get("index")) == base_index), None)
    if not base and bases:
        base = min(
            bases,
            key=lambda item: (
                (float((item.get("coords") or {}).get("x", 0)) - x) ** 2
                + (float((item.get("coords") or {}).get("y", 0)) - y) ** 2
            ),
        )
    if base:
        return base.get("displayName") or base.get("defaultName") or f"Base {base_index}"
    return f"Base {base_index} @ ({x:.0f}, {y:.0f})"


def work_card_for_pal(pal: dict, owner_counts: dict[str, int], selected_work: str = "") -> dict:
    work = work_for_pal(pal)
    name = pal.get("name", "")
    condensed_levels = fully_condensed_work_levels(work, name)
    projected_levels = projected_fully_condensed_work_levels(work)
    work_source = work_source_for(name)
    entries = work_entries(work, name)
    selected_level = as_int(work.get(selected_work)) if selected_work else max((as_int(work.get(k)) for k in WORK_LABELS), default=0)
    return {
        "key": pal.get("key", ""),
        "name": name,
        "types": pal.get("types", []),
        "icon": icon_url_for_key(pal.get("key", "")),
        "size": pal_size_for(name),
        "sizeGroup": SIZE_GROUPS.get(pal_size_for(name), "Unknown Size"),
        "sizeKnown": pal_size_for(name) != "Unknown",
        "selectedWork": selected_work,
        "selectedWorkLabel": WORK_LABELS.get(selected_work, ""),
        "selectedLevel": selected_level,
        "selectedFullyCondensedLevel": condensed_levels.get(selected_work) if selected_work else None,
        "selectedProjectedFullyCondensedLevel": projected_levels.get(selected_work) if selected_work else None,
        "work": entries,
        "workLevels": {entry["key"]: entry for entry in entries},
        "workCount": len(entries),
        "workCondensationSource": "verified" if work_source else "projected",
        "workCondensationSourceDetail": (work_source or {}).get("source", ""),
        "workCondensationSourceUrl": (work_source or {}).get("url", ""),
        "ownedCount": owner_counts.get(name, 0),
        "breedable": bool(pal.get("breedable", True)),
        "uniqueOnly": bool(pal.get("uniqueOnly", False)),
        "requiresOwnedSeed": requires_owned_seed_for_breeding(pal.get("key", "")),
    }


WORK_SPEED_PASSIVE_SCORE = {
    "Demon’s Hand": 90,
    "Remarkable Craftsmanship": 75,
    "Artisan": 50,
    "Work Slave": 30,
    "Lucky": 20,
    "Serious": 20,
    "Conceited": 10,
}

WORK_UPTIME_PASSIVE_SCORE = {
    "Insomnia": 30,
    "Vampiric": 25,
}

BASE_OPERATION_PASSIVE_SCORE = {
    "Mastery of Fasting": 20,
    "Diet Lover": 15,
    "Workaholic": 15,
    "Dainty Eater": 10,
    "Positive Thinker": 10,
    "Heart of the Immovable King": 8,
}

BASE_OPERATION_PASSIVE_PENALTY = {
    "Musclehead": 50,
    "Slacker": 30,
    "Clumsy": 10,
    "Hooligan": 10,
    "Bottomless Stomach": 15,
    "Destructive": 15,
    "Glutton": 10,
    "Unstable": 10,
}

WORK_RANK_PASSIVE_PATTERNS = {
    "kindling": "EmitFlame",
    "watering": "Watering",
    "planting": "Seeding",
    "electric": "GenerateElectricity",
    "handiwork": "Handcraft",
    "gathering": "Collection",
    "mining": "Mining",
    "farming": "MonsterFarm",
    "lumbering": "Deforest",
    "medicine": "ProductMedicine",
    "cooling": "Cool",
    "transporting": "Transport",
}


def pal_data_for_species(name: str) -> dict | None:
    key = STORE.name_to_key.get(normalize_species(name).lower())
    return next((pal for pal in STORE.breeding_data.get("pals", []) if pal.get("key") == key), None)


def passive_work_score_parts(passives: frozenset[str], types: list[str]) -> dict[str, int]:
    type_set = {str(t).lower() for t in types or []}
    is_dark = "dark" in type_set
    direct_speed = sum(WORK_SPEED_PASSIVE_SCORE.get(passive, 0) for passive in passives)
    uptime = 0 if is_dark else sum(WORK_UPTIME_PASSIVE_SCORE.get(passive, 0) for passive in passives)
    operations = sum(BASE_OPERATION_PASSIVE_SCORE.get(passive, 0) for passive in passives)
    harmful = sum(BASE_OPERATION_PASSIVE_PENALTY.get(passive, 0) for passive in passives)
    return {
        "directSpeed": direct_speed,
        "uptime": uptime,
        "operations": operations,
        "harmful": harmful,
        "total": direct_speed + uptime + operations - harmful,
    }


def passive_work_speed_score(passives: frozenset[str], types: list[str] | None = None) -> int:
    return passive_work_score_parts(passives, types or []).get("total", 0)


def passive_work_rank_bonus(row: dict[str, str], skill: str) -> int:
    pattern = WORK_RANK_PASSIVE_PATTERNS.get(skill, "")
    if not pattern:
        return 0
    passive_ids = row.get("passive_ids", "") or ""
    return 1 if f"WorkSuitabilityAddRank_{pattern}_1" in passive_ids else 0


def actual_owned_work_levels(row: dict[str, str], pal: dict) -> dict[str, int]:
    name = pal.get("name", "")
    base = work_for_pal(pal)
    full = fully_condensed_work_levels(base, name)
    stars = as_int(row.get("condensation_stars"))
    levels = {}
    for key in WORK_LABELS:
        base_level = as_int(base.get(key))
        if base_level <= 0:
            continue
        level = as_int(full.get(key), base_level) if stars >= 4 else base_level
        level += passive_work_rank_bonus(row, key)
        levels[key] = min(10, level)
    return levels


def work_entries_from_levels(levels: dict[str, int], maximum_levels: dict[str, int] | None = None) -> list[dict]:
    maximum_levels = maximum_levels or {}
    entries = []
    for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1]):
        level = as_int(levels.get(key))
        if level <= 0:
            continue
        entries.append({
            "key": key,
            "label": label,
            "level": level,
            "currentOnly": True,
            "fullyCondensedLevel": None,
            "projectedFullyCondensedLevel": None,
            "plannerCurrentLevel": level,
            "plannerMaximumLevel": max(level, as_int(maximum_levels.get(key), level)),
        })
    return entries


def maximum_owned_work_levels(row: dict[str, str], pal: dict) -> dict[str, int]:
    base = work_for_pal(pal)
    full = fully_condensed_work_levels(base, pal.get("name", ""))
    levels = {}
    for key in WORK_LABELS:
        base_level = as_int(base.get(key))
        if base_level <= 0:
            continue
        level = as_int(full.get(key), base_level) + passive_work_rank_bonus(row, key)
        levels[key] = min(10, level)
    return levels


def best_owned_work_levels(owner: str) -> dict[str, dict[str, int]]:
    best: dict[str, dict[str, int]] = {}
    for row in STORE.roster:
        if owner and row.get("owner") != owner:
            continue
        species = normalize_species(row.get("species", ""))
        pal = pal_data_for_species(species)
        if not pal:
            continue
        species_levels = best.setdefault(pal.get("name", species), {})
        for key, level in actual_owned_work_levels(row, pal).items():
            species_levels[key] = max(species_levels.get(key, 0), level)
    return best


def work_card_for_owned_row(row: dict[str, str]) -> dict | None:
    species = normalize_species(row.get("species", ""))
    pal = pal_data_for_species(species)
    if not pal:
        return None
    levels = actual_owned_work_levels(row, pal)
    if not levels:
        return None
    passives = split_passives(row.get("passives"))
    work_source = work_source_for(pal.get("name", ""))
    entries = work_entries_from_levels(levels, maximum_owned_work_levels(row, pal))
    location = display_owned_location(row.get("location", "") or "")
    score_parts = passive_work_score_parts(passives, pal.get("types", []))
    return {
        "key": pal.get("key", ""),
        "name": pal.get("name", species),
        "types": pal.get("types", []),
        "icon": icon_url_for_key(pal.get("key", "")),
        "size": pal_size_for(pal.get("name", species)),
        "sizeGroup": SIZE_GROUPS.get(pal_size_for(pal.get("name", species)), "Unknown Size"),
        "sizeKnown": pal_size_for(pal.get("name", species)) != "Unknown",
        "selectedWork": "",
        "selectedWorkLabel": "",
        "selectedLevel": max(levels.values(), default=0),
        "work": entries,
        "workLevels": {entry["key"]: entry for entry in entries},
        "workCount": len(entries),
        "workCondensationSource": "verified" if work_source else "projected",
        "workCondensationSourceDetail": (work_source or {}).get("source", ""),
        "workCondensationSourceUrl": (work_source or {}).get("url", ""),
        "ownedCount": 1,
        "breedable": bool(pal.get("breedable", True)),
        "uniqueOnly": bool(pal.get("uniqueOnly", False)),
        "plannerPassives": sorted(passives),
        "plannerPassiveSpeedScore": score_parts["total"],
        "plannerPassiveScoreParts": score_parts,
        "plannerLocation": location,
        "plannerCondensationStars": as_int(row.get("condensation_stars")),
        "plannerLevel": as_int(row.get("level")),
        "plannerGender": row.get("gender", ""),
        "plannerInstanceId": row.get("instance_id", ""),
        "rightNow": True,
    }


def planner_auto_target(skill: str, demand_count: int, demand: dict[str, int]) -> int:
    if demand_count <= 0:
        return 0
    if skill in {"cooling", "medicine"}:
        return 1
    if skill == "transporting":
        productive = sum(demand.get(k, 0) for k in ("mining", "farming", "planting", "gathering", "lumbering"))
        return min(AUTO_TARGET_CAPS.get(skill, 5), max(1, math.ceil(productive / 3)))
    return min(AUTO_TARGET_CAPS.get(skill, 3), max(1, math.ceil(demand_count / 2)))


def build_base_planner(payload: dict) -> dict:
    base_id = payload.get("baseId", "")
    owner = payload.get("owner", "")
    settings = payload.get("settings") or {}
    planner_mode = payload.get("plannerMode") if payload.get("plannerMode") in {"ideal", "right_now"} else "ideal"
    owned_only = planner_mode == "right_now"
    max_workers = min(15, max(1, as_int(payload.get("maxWorkers"), 15)))
    bases_payload = base_work_sites_payload()
    if not bases_payload.get("ok"):
        return bases_payload
    base = next((item for item in bases_payload.get("bases", []) if item.get("id") == base_id), None) or (bases_payload.get("bases") or [None])[0]
    if not base:
        return {"ok": False, "error": "No bases were found in the decoded save.", "bases": []}

    demand = dict(base.get("demand") or {})
    if any(demand.get(k, 0) for k in ("mining", "farming", "planting", "gathering", "lumbering")):
        demand["transporting"] = max(demand.get("transporting", 0), 1)

    targets = {}
    for key in WORK_LABELS:
        cfg = settings.get(key) or {}
        enabled = bool(cfg.get("enabled", True))
        if not enabled:
            targets[key] = {"enabled": False, "min": 0, "max": 0, "auto": 0, "demand": as_int(demand.get(key)), "autoCap": 0}
            continue
        auto = planner_auto_target(key, as_int(demand.get(key)), demand)
        auto_cap = min(max_workers, max(auto, AUTO_TARGET_CAPS.get(key, 3))) if auto else 0
        min_raw = cfg.get("min", None)
        max_raw = cfg.get("max", None)
        explicit_min = min_raw not in (None, "")
        explicit_max = max_raw not in (None, "")
        default_min = 1 if auto > 0 else 0
        min_value = as_int(min_raw, default_min)
        max_value = as_int(max_raw, max_workers) if explicit_max else max_workers
        max_value = min(max_workers, max(min_value, max_value))
        targets[key] = {
            "enabled": True,
            "min": min_value,
            "max": max_value,
            "auto": auto,
            "demand": as_int(demand.get(key)),
            "autoCap": auto_cap,
            "explicitMin": explicit_min,
            "explicitMax": explicit_max,
        }

    owner_counts = owned_species_counts(owner)
    owner_work_levels = best_owned_work_levels(owner)
    candidates = []
    enabled_skills = {key for key, cfg in targets.items() if cfg["enabled"] and (cfg["max"] > 0 or cfg["min"] > 0)}
    if owned_only:
        for row in STORE.roster:
            if owner and row.get("owner") != owner:
                continue
            card = work_card_for_owned_row(row)
            if not card:
                continue
            levels = {entry["key"]: as_int(entry.get("level")) for entry in card["work"]}
            if not any(levels.get(skill, 0) > 0 for skill in enabled_skills):
                continue
            card["plannerLevels"] = levels
            candidates.append(card)
    else:
        for pal in STORE.breeding_data.get("pals", []):
            card = work_card_for_pal(pal, owner_counts)
            best_levels = owner_work_levels.get(card.get("name", ""), {})
            for entry in card["work"]:
                owned_level = as_int(best_levels.get(entry["key"]))
                if owned_level > 0:
                    entry["plannerCurrentLevel"] = owned_level
                    entry["plannerMaximumLevel"] = max(
                        owned_level,
                        as_int(entry.get("fullyCondensedLevel") or entry.get("level")),
                    )
            levels = {entry["key"]: as_int(entry.get("fullyCondensedLevel") or entry.get("level")) for entry in card["work"]}
            if not any(levels.get(skill, 0) > 0 for skill in enabled_skills):
                continue
            card["plannerLevels"] = levels
            candidates.append(card)

    def best_for_role(skill: str, used_counts: dict[str, int]) -> dict | None:
        pool = [card for card in candidates if as_int(card.get("plannerLevels", {}).get(skill)) > 0]
        if owned_only:
            used_instances = {key for key, value in used_counts.items() if key.startswith("instance:") and value > 0}
            pool = [card for card in pool if f"instance:{card.get('plannerInstanceId', '')}" not in used_instances]
        if not pool:
            return None
        def score(card: dict) -> tuple:
            levels = card.get("plannerLevels", {})
            role_level = as_int(levels.get(skill))
            extra_enabled = sum(as_int(levels.get(other)) for other in enabled_skills if other != skill)
            off_role_count = sum(1 for other, level in levels.items() if other != skill and level > 0)
            owned_bonus = 1 if card.get("ownedCount") else 0
            repeat_penalty = used_counts.get(card.get("name", ""), 0)
            score_parts = card.get("plannerPassiveScoreParts") or {}
            direct_speed = as_int(score_parts.get("directSpeed"))
            uptime = as_int(score_parts.get("uptime"))
            operations = as_int(score_parts.get("operations"))
            harmful = as_int(score_parts.get("harmful"))
            total_passive_score = as_int(score_parts.get("total"))
            current_base_bonus = 1 if str(card.get("plannerLocation", "")).startswith("Base") else 0
            size_penalty = SIZE_ORDER.get(card.get("size"), 3)
            return (role_level, direct_speed, uptime, operations, -harmful, total_passive_score, current_base_bonus, owned_bonus, -repeat_penalty, -off_role_count, extra_enabled, -size_penalty, card.get("name", ""))
        return max(pool, key=score)

    role_slots: list[str] = []
    role_weights = {
        "mining": 14,
        "planting": 12,
        "watering": 12,
        "gathering": 11,
        "handiwork": 10,
        "kindling": 9,
        "electric": 9,
        "lumbering": 8,
        "cooling": 7,
        "farming": 7,
        "transporting": 6,
        "medicine": 4,
    }

    def role_has_candidate(skill: str) -> bool:
        return any(as_int(card.get("plannerLevels", {}).get(skill)) > 0 for card in candidates)

    def role_sort_key(skill: str) -> tuple:
        cfg = targets.get(skill, {})
        return (
            role_weights.get(skill, 1),
            as_int(cfg.get("demand")),
            as_int(cfg.get("auto")),
            WORK_LABELS.get(skill, skill),
        )

    active_roles = [
        key for key, cfg in targets.items()
        if cfg.get("enabled") and cfg.get("max", 0) > 0 and (cfg.get("min", 0) > 0 or cfg.get("auto", 0) > 0 or cfg.get("demand", 0) > 0) and role_has_candidate(key)
    ]

    def add_role(skill: str, amount: int = 1) -> None:
        cfg = targets.get(skill, {})
        for _ in range(max(0, amount)):
            if len(role_slots) >= max_workers:
                return
            if role_slots.count(skill) >= cfg.get("max", max_workers):
                return
            role_slots.append(skill)

    for key in sorted(active_roles, key=role_sort_key, reverse=True):
        cfg = targets[key]
        if cfg.get("explicitMin") and cfg.get("min", 0) > 0:
            add_role(key, cfg["min"])

    for key in sorted(active_roles, key=role_sort_key, reverse=True):
        cfg = targets[key]
        if len(role_slots) >= max_workers:
            break
        if role_slots.count(key) == 0 and (cfg.get("demand", 0) > 0 or cfg.get("auto", 0) > 0):
            add_role(key)

    def next_role(prefer_soft_caps: bool) -> str | None:
        expandable = []
        for key in active_roles:
            cfg = targets[key]
            current = role_slots.count(key)
            if current >= cfg.get("max", max_workers):
                continue
            soft_cap = cfg.get("autoCap", 0) or cfg.get("auto", 0) or 1
            if prefer_soft_caps and current >= soft_cap:
                continue
            target_need = max(0, cfg.get("min", 0) - current)
            soft_need = max(0, soft_cap - current)
            demand_bonus = min(6, as_int(cfg.get("demand")))
            priority = (role_weights.get(key, 1) * 10) + demand_bonus
            if target_need > 0:
                priority += 1000
            elif soft_need > 0:
                priority += 100
            priority -= current * 8
            expandable.append((priority, -current, role_sort_key(key), key))
        if not expandable:
            return None
        expandable.sort(reverse=True)
        return expandable[0][3]

    while len(role_slots) < max_workers:
        key = next_role(prefer_soft_caps=True) or next_role(prefer_soft_caps=False)
        if not key:
            break
        add_role(key)

    selected = []
    covered = {key: 0 for key in WORK_LABELS}
    used_counts: dict[str, int] = {}
    for idx, skill in enumerate(role_slots[:max_workers], 1):
        card = best_for_role(skill, used_counts)
        if not card:
            continue
        item = json.loads(json.dumps(card))
        item["plannerRole"] = skill
        item["plannerSlot"] = idx
        item["selectedWork"] = skill
        item["plannerReasons"] = [f"Primary: {WORK_LABELS[skill]} Lv. {as_int(item.get('plannerLevels', {}).get(skill))}"]
        for other, level in sorted(item.get("plannerLevels", {}).items(), key=lambda entry: (-as_int(entry[1]), WORK_LABELS.get(entry[0], entry[0]))):
            if other != skill and level > 0 and targets.get(other, {}).get("enabled"):
                item["plannerReasons"].append(f"Also {WORK_LABELS[other]} Lv. {level}")
            if len(item["plannerReasons"]) >= 4:
                break
        selected.append(item)
        used_counts[item.get("name", "")] = used_counts.get(item.get("name", ""), 0) + 1
        if item.get("plannerInstanceId"):
            used_counts[f"instance:{item.get('plannerInstanceId')}"] = 1
        if covered.get(skill, 0) < targets.get(skill, {}).get("max", max_workers):
            covered[skill] = covered.get(skill, 0) + 1

    gaps = []
    for key, cfg in targets.items():
        if cfg["enabled"] and cfg["min"] > 0 and covered.get(key, 0) < cfg["min"]:
            gaps.append({"key": key, "label": WORK_LABELS[key], "wanted": cfg["min"], "covered": covered.get(key, 0)})

    return {
        "ok": True,
        "base": base,
        "owner": owner,
        "maxWorkers": max_workers,
        "plannerMode": planner_mode,
        "ownedOnly": owned_only,
        "targets": targets,
        "covered": {key: value for key, value in covered.items() if value > 0},
        "recommendations": selected,
        "roleSlots": role_slots[:max_workers],
        "gaps": gaps,
        "summary": f"{len(selected)} recommended worker slot(s) for {base.get('displayName')}.",
    }


def row_to_state(row: dict[str, str], store: DataStore) -> State | None:
    species = normalize_species(row.get("species", ""))
    key = store.name_to_key.get(species.lower())
    if not key:
        return None
    raw_location = row.get("location", "") or ""
    location = display_owned_location(raw_location)
    pos = palbox_position(raw_location)
    base_slot_number = base_slot(raw_location)
    hp_iv = as_int(row.get("hp_iv"))
    attack_iv = as_int(row.get("attack_iv"))
    defense_iv = as_int(row.get("defense_iv"))
    iv_total = hp_iv + attack_iv + defense_iv
    nick = row.get("nickname") or species
    label = f"{species} {row.get('gender') or '?'} L{row.get('level') or 0} [{nick}] IV {row.get('hp_iv')}/{row.get('attack_iv')}/{row.get('defense_iv')}"
    if pos["box"]:
        label += f" Box {pos['box']} Slot {pos['slot']}"
    elif base_slot_number is not None:
        label += f" {location} Slot {base_slot_number}"
    else:
        label += f" {location}"
    return State(
        species_key=key,
        species=species,
        passives=split_passives(row.get("passives")),
        gender=row.get("gender") or "Unknown",
        steps=0,
        breed_count=0,
        hp_iv=hp_iv,
        attack_iv=attack_iv,
        defense_iv=defense_iv,
        iv_total=iv_total,
        iv_sources=1,
        label=label,
        location=location,
        box=pos["box"],
        slot=pos["slot"],
        base_slot=base_slot_number,
        base_workers_used=owned_location_base_penalty(raw_location),
        instance_id=row.get("instance_id") or "",
    )


def compatible(a: State, b: State) -> bool:
    fixed = {a.gender, b.gender}
    if "Either" in fixed or "Unknown" in fixed:
        return True
    return fixed == {"Male", "Female"}


def iv_sort_bits(s: State, iv_preference: str) -> tuple:
    if iv_preference == "highest_iv":
        return (-s.avg_iv, -s.avg_attack_iv)
    if iv_preference == "highest_attack":
        return (-s.avg_attack_iv, -s.avg_iv)
    if iv_preference == "balanced_iv":
        weakest = min(s.avg_hp_iv, s.avg_attack_iv, s.avg_defense_iv)
        return (-weakest, -s.avg_iv, -s.avg_attack_iv, -s.avg_hp_iv, -s.avg_defense_iv)
    if iv_preference == "survival_iv":
        return (-(s.avg_hp_iv + s.avg_defense_iv) / 2, -s.avg_hp_iv, -s.avg_defense_iv, -s.avg_attack_iv)
    return ()


def owned_location_base_penalty(location: str) -> int:
    lower = (location or "").lower()
    if lower.startswith("base "):
        return 1
    return 0


def state_score(s: State, target: frozenset[str], allowed: frozenset[str], iv_preference: str = "none"):
    desired = len(s.passives & target)
    junk = len(s.passives - target - allowed)
    missing = len(target - s.passives)
    return (-desired, junk, missing, s.breed_count, s.steps, *iv_sort_bits(s, iv_preference), s.label)


def compact_states(states: list[State], target: frozenset[str], allowed: frozenset[str], per_species=30, iv_preference: str = "none") -> list[State]:
    grouped: dict[str, dict[tuple[frozenset[str], str], State]] = {}
    for s in states:
        by_pool = grouped.setdefault(s.species_key, {})
        key = (s.passives, s.gender)
        existing = by_pool.get(key)
        if existing is None or state_score(s, target, allowed, iv_preference) < state_score(existing, target, allowed, iv_preference):
            by_pool[key] = s
    kept = []
    for group in grouped.values():
        kept.extend(sorted(group.values(), key=lambda s: state_score(s, target, allowed, iv_preference))[:per_species])
    return kept


def target_complete(s: State, target: frozenset[str]) -> bool:
    return target <= s.passives


def junk_count(s: State, target: frozenset[str], allowed: frozenset[str]) -> int:
    return len(s.passives - target - allowed)


def result_sort_key(s: State, target: frozenset[str], allowed: frozenset[str], *, fastest: bool = False, iv_preference: str = "none", prefer_storage: bool = False):
    desired = len(s.passives & target)
    junk = junk_count(s, target, allowed)
    missing = len(target - s.passives)
    storage_bits = (s.base_workers_used,) if prefer_storage else ()
    if fastest:
        return (missing, s.breed_count, s.steps, junk, -desired, *iv_sort_bits(s, iv_preference), *storage_bits, s.label)
    return (missing, junk, s.breed_count, s.steps, -desired, *iv_sort_bits(s, iv_preference), *storage_bits, s.label)


def owned_states_for_owner(owner: str) -> list[State]:
    owned = [row_to_state(r, STORE) for r in STORE.roster if (r.get("owner") or "").lower() == owner]
    return [s for s in owned if s]


def search_states(
    owned: list[State],
    target: frozenset[str],
    allowed: frozenset[str],
    *,
    strict: bool,
    max_steps: int,
    per_species: int,
    global_limit: int,
    iv_preference: str = "none",
) -> list[State]:
    seed = [s for s in owned if not strict or not (s.passives - target - allowed)]
    states = compact_states(seed, target, allowed, per_species=per_species, iv_preference=iv_preference)
    all_states = list(states)
    seen = {s.id for s in all_states}

    for depth in range(1, max_steps + 1):
        new_states: list[State] = []
        source = sorted(all_states, key=lambda s: state_score(s, target, allowed, iv_preference))[:global_limit]
        for a, b in combinations(source, 2):
            if not compatible(a, b):
                continue
            child = STORE.child_for(a.species_key, b.species_key)
            if not child:
                continue
            pool = frozenset(set(a.passives) | set(b.passives))
            if strict and (pool - target - allowed):
                continue
            child_name = STORE.pals[child].name
            s = State(
                species_key=child,
                species=child_name,
                passives=pool,
                gender="Either",
                steps=max(a.steps, b.steps) + 1,
                breed_count=a.breed_count + b.breed_count + 1,
                hp_iv=a.hp_iv + b.hp_iv,
                attack_iv=a.attack_iv + b.attack_iv,
                defense_iv=a.defense_iv + b.defense_iv,
                iv_total=a.iv_total + b.iv_total,
                iv_sources=a.iv_sources + b.iv_sources,
                label=f"Breed {child_name}",
                location="bred intermediate",
                box=None,
                slot=None,
                base_workers_used=a.base_workers_used + b.base_workers_used,
                parents=(a, b),
            )
            if s.id not in seen:
                seen.add(s.id)
                new_states.append(s)
        if not new_states:
            continue
        all_states = compact_states(all_states + new_states, target, allowed, per_species=per_species, iv_preference=iv_preference)
    return all_states


def top_donors_for_species(states: list[State], species_key: str, target: frozenset[str], allowed: frozenset[str], limit: int = 10, iv_preference: str = "none") -> list[State]:
    candidates = [s for s in states if s.species_key == species_key]
    candidates.sort(key=lambda s: result_sort_key(s, target, allowed, iv_preference=iv_preference))
    out: list[State] = []
    seen: set[tuple] = set()
    for s in candidates:
        key = (tuple(sorted(s.passives)), s.steps, s.breed_count, s.gender, s.label)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def final_parent_routes(states: list[State], target_key: str, target: frozenset[str], allowed: frozenset[str], limit: int = 180, iv_preference: str = "none") -> list[State]:
    routes: list[State] = []
    child_name = STORE.pals[target_key].name
    pairs = STORE.parent_pairs_for_child(target_key)
    donor_cache: dict[str, list[State]] = {}

    for left_key, right_key in pairs:
        left = donor_cache.setdefault(left_key, top_donors_for_species(states, left_key, target, allowed, iv_preference=iv_preference))
        right = donor_cache.setdefault(right_key, top_donors_for_species(states, right_key, target, allowed, iv_preference=iv_preference))
        if not left or not right:
            continue
        if left_key == right_key:
            pair_source = combinations(left, 2)
        else:
            pair_source = product(left, right)
        for a, b in pair_source:
            if a is b or not compatible(a, b):
                continue
            pool = frozenset(set(a.passives) | set(b.passives))
            route = State(
                species_key=target_key,
                species=child_name,
                passives=pool,
                gender="Either",
                steps=max(a.steps, b.steps) + 1,
                breed_count=a.breed_count + b.breed_count + 1,
                hp_iv=a.hp_iv + b.hp_iv,
                attack_iv=a.attack_iv + b.attack_iv,
                defense_iv=a.defense_iv + b.defense_iv,
                iv_total=a.iv_total + b.iv_total,
                iv_sources=a.iv_sources + b.iv_sources,
                label=f"Breed {child_name} via {STORE.pals[left_key].name} + {STORE.pals[right_key].name}",
                location="final parent route",
                box=None,
                slot=None,
                base_workers_used=a.base_workers_used + b.base_workers_used,
                parents=(a, b),
            )
            routes.append(route)

    routes.sort(key=lambda s: result_sort_key(s, target, allowed, iv_preference=iv_preference))
    return routes[:limit]

def walk_tree(s: State):
    yield s
    if s.parents:
        yield from walk_tree(s.parents[0])
        yield from walk_tree(s.parents[1])


def progress_leaf_score(s: State, target: frozenset[str], allowed: frozenset[str]) -> int:
    if s.parents or junk_count(s, target, allowed):
        return 0
    desired = len(s.passives & target)
    if target and target <= s.passives:
        return 120
    if desired >= max(1, len(target) - 1):
        return 70
    if desired >= 2:
        return 25
    return 0


def progress_species(owned: list[State], target: frozenset[str], allowed: frozenset[str]) -> set[str]:
    return {s.species_key for s in owned if progress_leaf_score(s, target, allowed) >= 70}


def progress_score(s: State, target: frozenset[str], allowed: frozenset[str], progressed_species: set[str]) -> int:
    score = 0
    if s.parents:
        for parent in s.parents:
            if parent.species_key in progressed_species:
                score += 500
    seen_leaves: set[tuple] = set()
    seen_species: set[str] = set()
    for node in walk_tree(s):
        if node.species_key in progressed_species and node.species_key not in seen_species:
            score += 30
            seen_species.add(node.species_key)
        if not node.parents:
            leaf_key = (node.species_key, node.gender, node.location, tuple(sorted(node.passives)))
            if leaf_key not in seen_leaves:
                score += progress_leaf_score(node, target, allowed)
                seen_leaves.add(leaf_key)
    return score


def progress_sort_key(s: State, target: frozenset[str], allowed: frozenset[str], progressed_species: set[str], iv_preference: str = "none"):
    desired = len(s.passives & target)
    missing = len(target - s.passives)
    junk = junk_count(s, target, allowed)
    return (missing, junk, s.breed_count, s.steps, -progress_score(s, target, allowed, progressed_species), -desired, *iv_sort_bits(s, iv_preference), s.label)


def progress_notes(s: State, target: frozenset[str], allowed: frozenset[str]) -> list[str]:
    notes = []
    progressed = []
    if s.parents:
        for parent in s.parents:
            if target <= parent.passives and not junk_count(parent, target, allowed):
                progressed.append(parent.species)
        for species in sorted(set(progressed)):
            notes.append(f"Continues clean {species} progress as a final parent line.")
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for node in walk_tree(s):
        if node.parents or junk_count(node, target, allowed):
            continue
        desired = sorted(node.passives & target)
        if len(desired) < max(2, len(target) - 1):
            continue
        key = (node.species, tuple(desired))
        if key in seen:
            continue
        seen.add(key)
        if target <= node.passives:
            notes.append(f"Reuses owned clean {node.species} with all desired passives ({node.gender}).")
        else:
            missing = sorted(target - node.passives)
            notes.append(f"Reuses owned clean {node.species} with {len(desired)}/{len(target)} desired; missing {', '.join(missing)}.")
        if len(notes) >= 3:
            break
    return notes


def tree_signature(s: State) -> tuple:
    if not s.parents:
        return ("owned", s.species_key, tuple(sorted(s.passives)), s.gender, s.location, s.box, s.slot)
    return (
        "bred",
        s.species_key,
        tuple(sorted(s.passives)),
        tuple(sorted((tree_signature(s.parents[0]), tree_signature(s.parents[1])), key=repr)),
    )


def unique_serialized(states: list[State], target: frozenset[str], allowed: frozenset[str], limit: int, *, fastest: bool = False, iv_preference: str = "none", progress_species_set: set[str] | None = None, intended_gender: str = "any", replacement_pool: list[State] | None = None) -> list[dict]:
    out = []
    seen: set[tuple] = set()
    progress_species_set = progress_species_set or set()
    if progress_species_set:
        ordered = sorted(states, key=lambda x: progress_sort_key(x, target, allowed, progress_species_set, iv_preference=iv_preference))
    else:
        ordered = sorted(states, key=lambda x: result_sort_key(x, target, allowed, fastest=fastest, iv_preference=iv_preference))
    for s in ordered:
        key = tree_signature(s)
        if key in seen:
            continue
        seen.add(key)
        item_state = substitute_storage_leaves(s, replacement_pool, target, allowed) if replacement_pool else s
        item = serialize_state(item_state, target, allowed, intended_gender, iv_preference)
        if progress_species_set:
            item["progressScore"] = progress_score(s, target, allowed, progress_species_set)
            item["progressNotes"] = progress_notes(s, target, allowed)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def gender_matches(s: State, preference: str) -> bool:
    return preference in {"", "any", "Any", None} or s.gender == preference or s.gender == "Either"


def gender_filtered(states: list[State], preference: str) -> list[State]:
    return [s for s in states if gender_matches(s, preference)]


def ready_to_finish_states(
    owned_target_states: list[State],
    final_target: frozenset[str],
    implant_passives: frozenset[str],
    gender_preference: str,
) -> list[State]:
    if not final_target or not implant_passives:
        return []
    candidates = []
    for state in gender_filtered(owned_target_states, gender_preference):
        missing = final_target - state.passives
        if not missing:
            continue
        if missing <= implant_passives and final_target <= (state.passives | implant_passives):
            candidates.append(state)
    return candidates


def best_storage_substitute(s: State, owned: list[State], target: frozenset[str], allowed: frozenset[str]) -> State | None:
    if s.parents or not s.base_workers_used:
        return None
    required = s.passives & target
    if not required:
        return None
    candidates = [
        candidate for candidate in owned
        if (
            not candidate.parents
            and not candidate.base_workers_used
            and candidate.species_key == s.species_key
            and candidate.gender == s.gender
            and required <= candidate.passives
        )
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda candidate: state_score(candidate, target, allowed))[0]


def substitute_storage_leaves(s: State, owned: list[State], target: frozenset[str], allowed: frozenset[str]) -> State:
    if not s.parents:
        return best_storage_substitute(s, owned, target, allowed) or s
    parents = (
        substitute_storage_leaves(s.parents[0], owned, target, allowed),
        substitute_storage_leaves(s.parents[1], owned, target, allowed),
    )
    pool = frozenset(set(parents[0].passives) | set(parents[1].passives))
    hp_iv = parents[0].hp_iv + parents[1].hp_iv
    attack_iv = parents[0].attack_iv + parents[1].attack_iv
    defense_iv = parents[0].defense_iv + parents[1].defense_iv
    return replace(
        s,
        passives=pool,
        hp_iv=hp_iv,
        attack_iv=attack_iv,
        defense_iv=defense_iv,
        iv_total=hp_iv + attack_iv + defense_iv,
        iv_sources=parents[0].iv_sources + parents[1].iv_sources,
        base_workers_used=parents[0].base_workers_used + parents[1].base_workers_used,
        parents=parents,
    )


def build_group(slug: str, title: str, description: str, states: list[State], target_key: str, target: frozenset[str], allowed: frozenset[str], *, fastest: bool = False, complete_only: bool = True, iv_preference: str = "none", intended_gender: str = "any", replacement_pool: list[State] | None = None) -> dict:
    matches = [s for s in states if s.species_key == target_key]
    if complete_only:
        matches = [s for s in matches if target_complete(s, target)]
    return {
        "slug": slug,
        "title": title,
        "description": description,
        "results": unique_serialized(matches, target, allowed, 6, fastest=fastest, iv_preference=iv_preference, intended_gender=intended_gender, replacement_pool=replacement_pool),
    }


def work_speed_profile_scores(include_insomnia: bool = False) -> dict[str, int]:
    scores = dict(WORK_SPEED_PASSIVE_SCORE)
    if include_insomnia:
        scores["Insomnia"] = WORK_UPTIME_PASSIVE_SCORE["Insomnia"]
    return scores


def work_speed_passive_order(passives, scores: dict[str, int] | None = None) -> list[str]:
    scores = scores or WORK_SPEED_PASSIVE_SCORE
    return sorted(
        (passive for passive in passives if passive in scores),
        key=lambda passive: (-scores[passive], passive),
    )


def owned_state_identity(state: State) -> tuple:
    return (
        state.species_key,
        state.gender,
        state.passives,
        state.label,
        state.location,
        state.base_slot,
        state.instance_id,
        state.hp_iv,
        state.attack_iv,
        state.defense_iv,
        state.iv_sources,
    )


def restore_profile_tree(state: State, originals: dict[tuple, State], desired: frozenset[str]) -> State:
    if not state.parents:
        return originals.get(owned_state_identity(state), state)
    parents = (
        restore_profile_tree(state.parents[0], originals, desired),
        restore_profile_tree(state.parents[1], originals, desired),
    )
    pool = frozenset(set(parents[0].passives) | set(parents[1].passives))
    hp_iv = parents[0].hp_iv + parents[1].hp_iv
    attack_iv = parents[0].attack_iv + parents[1].attack_iv
    defense_iv = parents[0].defense_iv + parents[1].defense_iv
    return replace(
        state,
        passives=pool,
        hp_iv=hp_iv,
        attack_iv=attack_iv,
        defense_iv=defense_iv,
        iv_total=hp_iv + attack_iv + defense_iv,
        iv_sources=parents[0].iv_sources + parents[1].iv_sources,
        base_workers_used=parents[0].base_workers_used + parents[1].base_workers_used,
        parents=parents,
    )


def best_work_speed_profile(
    owned: list[State],
    target_key: str,
    gender_preference: str,
    include_insomnia: bool = False,
    priority_passive_groups: list[list[str]] | None = None,
    implant_passives: set[str] | None = None,
) -> dict:
    target_is_dark = "dark" in {str(t).lower() for t in species_types_for_key(target_key)}
    force_insomnia = include_insomnia and not target_is_dark
    scores = work_speed_profile_scores(force_insomnia)
    implant_passives = set(implant_passives or set())
    priority_groups = [
        list(dict.fromkeys(passive for passive in group if passive))
        for group in (priority_passive_groups or [])
    ]
    priority_groups = [group for group in priority_groups if group]
    priority_options = [passive for group in priority_groups for passive in group]
    for passive in priority_options:
        scores.setdefault(passive, 0)
    ideal = []
    for group in priority_groups:
        passive = group[0]
        if passive not in ideal:
            ideal.append(passive)
    if force_insomnia:
        ideal.extend(passive for passive in work_speed_passive_order(WORK_SPEED_PASSIVE_SCORE, scores) if passive not in ideal)
        ideal = ideal[:3]
        if "Insomnia" not in ideal:
            ideal.append("Insomnia")
    else:
        ideal.extend(passive for passive in work_speed_passive_order(scores, scores) if passive not in ideal)
        ideal = ideal[:4]
    available = frozenset(
        passive
        for state in owned
        for passive in state.passives
        if passive in scores
    ) | frozenset(passive for passive in implant_passives if passive in scores)
    if not available:
        return {"ideal": ideal, "selected": [], "route": None, "score": 0}

    breeding_available = frozenset(passive for passive in available if passive not in implant_passives)
    projected_owned = [
        replace(state, passives=frozenset(state.passives & breeding_available))
        for state in owned
    ]
    originals = {
        owned_state_identity(projected): original
        for original, projected in zip(owned, projected_owned)
    }
    states = search_states(
        projected_owned,
        breeding_available,
        frozenset(),
        strict=False,
        max_steps=3,
        per_species=64,
        global_limit=900,
    )
    routes = states + final_parent_routes(
        states,
        target_key,
        breeding_available,
        frozenset(),
        limit=500,
    )
    candidates = []
    for state in gender_filtered(routes, gender_preference):
        if state.species_key != target_key:
            continue
        forced = []
        priority_rank = 0
        available_on_candidate = set(state.passives) | implant_passives
        for group in priority_groups:
            selected_priority = next((passive for passive in group if passive in available_on_candidate), None)
            if selected_priority:
                forced.append(selected_priority)
                priority_rank += group.index(selected_priority)
            else:
                priority_rank += len(group)
        has_forced_insomnia = force_insomnia and "Insomnia" in available_on_candidate
        if force_insomnia and not has_forced_insomnia:
            priority_rank += 1
        speed_slots = 3 if has_forced_insomnia else 4
        selected = forced + [
            passive
            for passive in work_speed_passive_order(available_on_candidate, scores)
            if passive not in forced and passive != "Insomnia"
        ][:max(0, speed_slots - len(forced))]
        if has_forced_insomnia and "Insomnia" not in selected:
            selected.append("Insomnia")
        if not selected:
            continue
        candidates.append((
            priority_rank,
            -sum(scores[passive] for passive in selected),
            -len(selected),
            len(state.passives - set(selected)),
            state.breed_count,
            state.steps,
            state.label,
            selected,
            state,
        ))
    if not candidates:
        return {"ideal": ideal, "selected": [], "route": None, "score": 0}

    best = min(candidates, key=lambda item: item[:-2])
    selected = best[-2]
    desired = frozenset(selected)
    return {
        "ideal": ideal,
        "selected": selected,
        "route": restore_profile_tree(best[-1], originals, desired),
        "score": sum(scores[passive] for passive in selected),
        "scores": scores,
    }


def profile_passives_payload(payload: dict) -> dict:
    owner = (payload.get("owner") or "David").lower()
    target_name = (payload.get("target") or "").strip()
    target_key = STORE.name_to_key.get(target_name.lower())
    if not target_key:
        return {"ok": False, "error": f"Unknown target species: {target_name}"}
    profile = payload.get("breedingProfile") or "work_speed"
    if profile not in {"work_speed", "ranch_drops_focus"}:
        return {"ok": False, "error": f"Profile is not automatic: {profile}"}
    priority_passive_groups = [["Ranch Master"], ["Farmhand"]] if profile == "ranch_drops_focus" else []
    result = best_work_speed_profile(
        owned_states_for_owner(owner),
        target_key,
        payload.get("genderPreference") or "any",
        include_insomnia=bool(payload.get("includeInsomnia")),
        priority_passive_groups=priority_passive_groups,
    )
    return {
        "ok": True,
        "target": STORE.pals[target_key].name,
        "owner": owner,
        "breedingProfile": profile,
        "ideal": result.get("ideal", []),
        "selected": result.get("selected", []),
        "score": result.get("score", 0),
    }


def build_plan(payload: dict) -> dict:
    owner = (payload.get("owner") or "David").lower()
    target_name = (payload.get("target") or "").strip()
    target_key = STORE.name_to_key.get(target_name.lower())
    if not target_key:
        return {"error": f"Unknown target species: {target_name}"}
    final_target = canonical_passives(payload.get("passives", []))
    include_implants = bool(payload.get("includeImplants"))
    inventory_implants = available_implant_passives() if include_implants else set()
    implant_passives = (canonical_passives(payload.get("implantPassives", [])) | inventory_implants) & final_target
    target = frozenset(final_target - implant_passives)
    allowed = canonical_passives(payload.get("allowedExtras", [])) | implant_passives
    gender_preference = payload.get("genderPreference") or "any"
    iv_preference = "none"
    route_preference = payload.get("routePreference") or "best_overall"
    breeding_profile = payload.get("breedingProfile") or "manual"
    owned = owned_states_for_owner(owner)
    work_speed_profile = None
    profile_route = None
    if breeding_profile in {"work_speed", "ranch_drops_focus"}:
        priority_passive_groups = [["Ranch Master"], ["Farmhand"]] if breeding_profile == "ranch_drops_focus" else []
        work_speed_profile = best_work_speed_profile(
            owned,
            target_key,
            gender_preference,
            include_insomnia="Insomnia" in final_target,
            priority_passive_groups=priority_passive_groups,
            implant_passives=inventory_implants,
        )
        if work_speed_profile["selected"]:
            final_target = frozenset(work_speed_profile["selected"])
            implant_passives = (implant_passives | inventory_implants) & final_target
            target = frozenset(final_target - implant_passives)
            allowed = allowed | implant_passives
            profile_route = work_speed_profile["route"]
    progressed = progress_species(owned, target, allowed)

    clean_states = search_states(owned, target, allowed, strict=True, max_steps=4, per_species=8, global_limit=450, iv_preference=iv_preference)
    practical_states = search_states(owned, target, allowed, strict=False, max_steps=3, per_species=10, global_limit=550, iv_preference=iv_preference)
    fastest_states = search_states(owned, target, allowed, strict=False, max_steps=2, per_species=10, global_limit=450, iv_preference=iv_preference)
    clean_routes = clean_states + final_parent_routes(clean_states, target_key, target, allowed, iv_preference=iv_preference)
    practical_routes = practical_states + final_parent_routes(practical_states, target_key, target, allowed, iv_preference=iv_preference)
    fastest_routes = fastest_states + final_parent_routes(fastest_states, target_key, target, allowed, iv_preference=iv_preference)
    if profile_route:
        clean_routes.append(profile_route)
        practical_routes.append(profile_route)
        fastest_routes.append(profile_route)
    owned_target_states = [s for s in owned if s.species_key == target_key]
    owned_matching_target_states = [s for s in owned_target_states if target_complete(s, target)]
    owned_matching_target_for_gender = gender_filtered(owned_matching_target_states, gender_preference)
    ready_finish_states = ready_to_finish_states(
        owned_target_states,
        final_target,
        frozenset(implant_passives),
        gender_preference,
    )

    clean_group = build_group(
        "cleanest",
        "Cleanest Route",
        "No junk passives in the inherited pool. May take more setup breeds.",
        clean_routes,
        target_key,
        target,
        allowed,
        iv_preference=iv_preference,
        intended_gender=gender_preference,
        replacement_pool=owned,
    )
    fastest_group = build_group(
        "fastest",
        "Fastest Route",
        "Fewest total eggs with all desired passives present, even if the passive pool is messy.",
        fastest_routes,
        target_key,
        target,
        allowed,
        fastest=True,
        iv_preference=iv_preference,
        intended_gender=gender_preference,
        replacement_pool=owned,
    )
    practical_group = build_group(
        "least_junk",
        "Least-Junk Practical Route",
        "Middle ground: all desired passives, then fewer junk passives, then fewer setup breeds.",
        practical_routes,
        target_key,
        target,
        allowed,
        iv_preference=iv_preference,
        intended_gender=gender_preference,
        replacement_pool=owned,
    )
    existing_group = build_group(
        "existing_target",
        "Best Existing Target",
        "Owned target-species Pals that are already close and may be good consolidation parents.",
        owned_target_states,
        target_key,
        target,
        allowed,
        complete_only=False,
        iv_preference=iv_preference,
    )

    all_route_states = gender_filtered(practical_routes + clean_routes + fastest_routes, gender_preference)
    progress_candidates = [s for s in all_route_states if s.species_key == target_key and target_complete(s, target)]
    progress_group = {
        "slug": "continue_progress",
        "title": "Continue Progress",
        "description": "Favors clean owned 3/4 or 4/4 intermediate work when you rerun the same target/passives after syncing.",
        "results": unique_serialized(progress_candidates, target, allowed, 6, iv_preference=iv_preference, progress_species_set=progressed, intended_gender=gender_preference, replacement_pool=owned),
    }

    recommended_pool = owned_matching_target_for_gender or owned_matching_target_states or []
    recommended_states = [s for s in recommended_pool + all_route_states if s.species_key == target_key and target_complete(s, target)]
    if route_preference == "continue_progress" and progress_group["results"]:
        recommended = progress_group["results"][:3]
        recommended_description = "Best continuation of your synced progress for the same target/passives."
    else:
        recommended = unique_serialized(recommended_states, target, allowed, 3, iv_preference=iv_preference, intended_gender=gender_preference, replacement_pool=owned)
        recommended_description = "Best practical option from the searches below."
    achievable = bool(recommended)
    profile_ideal = work_speed_profile["ideal"] if work_speed_profile else []
    profile_selected = work_speed_profile["selected"] if work_speed_profile else []
    profile_score = work_speed_profile["score"] if work_speed_profile else 0
    profile_disclaimer = ""
    if work_speed_profile and profile_selected and profile_selected != profile_ideal:
        available = {passive for state in owned for passive in state.passives}
        reasons = []
        for passive in profile_ideal:
            if passive in profile_selected:
                continue
            if passive not in available and passive not in inventory_implants:
                reasons.append(f"{passive} is not owned or available as an implant")
            else:
                reasons.append(f"{passive} could not be included in a stronger reachable combination")
        profile_scores = work_speed_profile.get("scores", WORK_SPEED_PASSIVE_SCORE)
        ideal_score = sum(profile_scores[passive] for passive in profile_ideal)
        profile_disclaimer = (
            f"Using the fastest reachable combination (+{profile_score}% work speed). "
            f"The absolute +{ideal_score}% combination was not selected because "
            + "; ".join(reasons)
            + "."
        )
    groups = [
        {
            "slug": "recommended",
            "title": "Recommended",
            "description": recommended_description,
            "results": recommended,
        },
    ]
    if route_preference == "continue_progress":
        groups.append(progress_group)
    groups.extend([
        clean_group,
        fastest_group,
        practical_group,
        existing_group,
    ])
    return {
        "target": STORE.pals[target_key].name,
        "owner": owner,
        "requestedPassives": sorted(target),
        "finalPassives": sorted(final_target),
        "implantPassives": sorted(implant_passives),
        "allowedExtras": sorted(allowed),
        "ownedCount": len(owned),
        "genderPreference": gender_preference,
        "ivPreference": iv_preference,
        "routePreference": route_preference,
        "breedingProfile": breeding_profile,
        "achievable": achievable,
        "profileIdealPassives": profile_ideal,
        "profileSelectedPassives": profile_selected,
        "profileWorkSpeedBonus": profile_score,
        "profileDisclaimer": profile_disclaimer,
        "progressedSpecies": sorted(STORE.pals[key].name for key in progressed if key in STORE.pals),
        "alreadyOwned": {
            "count": len(owned_matching_target_states),
            "matchingGenderCount": len(owned_matching_target_for_gender),
            "results": unique_serialized(owned_matching_target_for_gender or owned_matching_target_states, target, allowed, 6, iv_preference=iv_preference, intended_gender=gender_preference),
        },
        "readyToFinish": {
            "count": len(ready_finish_states),
            "results": unique_serialized(ready_finish_states, final_target, implant_passives, 6, iv_preference=iv_preference, intended_gender=gender_preference),
        },
        "groups": groups,
        "results": recommended,
    }



def iv_goal_score(s: State, goal: str) -> tuple:
    if goal == "attack":
        return (s.avg_attack_iv, s.avg_iv, s.avg_hp_iv, s.avg_defense_iv)
    if goal == "survival":
        return ((s.avg_hp_iv + s.avg_defense_iv) / 2, s.avg_hp_iv, s.avg_defense_iv, s.avg_attack_iv)
    if goal == "highest":
        return (s.avg_iv, s.avg_attack_iv, s.avg_hp_iv, s.avg_defense_iv)
    weakest = min(s.avg_hp_iv, s.avg_attack_iv, s.avg_defense_iv)
    return (weakest, s.avg_iv, s.avg_attack_iv, s.avg_hp_iv, s.avg_defense_iv)


def iv_goal_pair_score(a: State, b: State, goal: str) -> tuple:
    max_hp = max(a.avg_hp_iv, b.avg_hp_iv)
    max_attack = max(a.avg_attack_iv, b.avg_attack_iv)
    max_defense = max(a.avg_defense_iv, b.avg_defense_iv)
    coverage_avg = (max_hp + max_attack + max_defense) / 3
    parent_avg = (a.avg_iv + b.avg_iv) / 2
    if goal == "attack":
        return (max_attack, coverage_avg, parent_avg, max_hp, max_defense)
    if goal == "survival":
        return ((max_hp + max_defense) / 2, max_hp, max_defense, max_attack, coverage_avg, parent_avg)
    if goal == "highest":
        return (coverage_avg, parent_avg, max_attack, max_hp, max_defense)
    weakest = min(max_hp, max_attack, max_defense)
    return (weakest, coverage_avg, parent_avg, max_attack, max_hp, max_defense)


def iv_100_support(a: State, b: State) -> dict[str, int]:
    return {
        "hp": int(round(a.avg_hp_iv) >= 100) + int(round(b.avg_hp_iv) >= 100),
        "attack": int(round(a.avg_attack_iv) >= 100) + int(round(b.avg_attack_iv) >= 100),
        "defense": int(round(a.avg_defense_iv) >= 100) + int(round(b.avg_defense_iv) >= 100),
    }


def iv_100_score(a: State, b: State) -> tuple[int, int, int, float]:
    support = iv_100_support(a, b)
    covered = sum(1 for value in support.values() if value > 0)
    doubled = sum(1 for value in support.values() if value > 1)
    single = sum(1 for value in support.values() if value == 1)
    backup = (
        max(a.avg_hp_iv, b.avg_hp_iv)
        + max(a.avg_attack_iv, b.avg_attack_iv)
        + max(a.avg_defense_iv, b.avg_defense_iv)
    ) / 3
    return covered, doubled, single, backup


def serialize_iv_pal(s: State, target: frozenset[str], allowed: frozenset[str]) -> dict:
    location = display_owned_location(s.location)
    selection_id = s.instance_id or f"{s.species_key}|{s.gender}|{s.location}|{s.box}|{s.slot}|{s.label}"
    return {
        "instanceId": s.instance_id,
        "selectionId": selection_id,
        "species": s.species,
        "gender": s.gender,
        "passives": sorted(s.passives),
        "desired": sorted(s.passives & target),
        "junk": sorted(s.passives - target - allowed),
        "missing": sorted(target - s.passives),
        "hpIv": round(s.avg_hp_iv, 1),
        "attackIv": round(s.avg_attack_iv, 1),
        "defenseIv": round(s.avg_defense_iv, 1),
        "avgIv": round(s.avg_iv, 1),
        "label": s.label,
        "location": location,
        "box": s.box,
        "slot": s.slot,
        "baseSlot": s.base_slot,
        "icon": icon_url_for_key(s.species_key),
    }


def serialize_iv_pair(a: State, b: State, target: frozenset[str], required: frozenset[str], allowed: frozenset[str]) -> dict:
    pool = frozenset(set(a.passives) | set(b.passives))
    best_hp = max(a.avg_hp_iv, b.avg_hp_iv)
    best_attack = max(a.avg_attack_iv, b.avg_attack_iv)
    best_defense = max(a.avg_defense_iv, b.avg_defense_iv)
    support = iv_100_support(a, b)
    return {
        "parents": [serialize_iv_pal(a, target, allowed), serialize_iv_pal(b, target, allowed)],
        "desired": sorted(pool & target),
        "missing": sorted(required - pool),
        "junk": sorted(pool - target - allowed),
        "passivePool": sorted(pool),
        "bestHpIv": round(best_hp, 1),
        "bestAttackIv": round(best_attack, 1),
        "bestDefenseIv": round(best_defense, 1),
        "bestAvgIv": round((best_hp + best_attack + best_defense) / 3, 1),
        "parentAvgIv": round((a.avg_iv + b.avg_iv) / 2, 1),
        "goalScore": round((best_hp + best_attack + best_defense) / 3, 1),
        "hp100Support": support["hp"],
        "attack100Support": support["attack"],
        "defense100Support": support["defense"],
        "perfectCoverage": sum(1 for value in support.values() if value > 0),
        "doublePerfectCoverage": sum(1 for value in support.values() if value > 1),
        "clean": not (pool - target - allowed),
        "compatible": compatible(a, b),
    }


def improves_selected_iv(candidate: State, selected: State) -> bool:
    return (
        candidate.avg_hp_iv > selected.avg_hp_iv
        or candidate.avg_attack_iv > selected.avg_attack_iv
        or candidate.avg_defense_iv > selected.avg_defense_iv
    )


def build_iv_plan(payload: dict) -> dict:
    owner = (payload.get("owner") or "David").lower()
    target_name = (payload.get("target") or "").strip()
    target_key = STORE.name_to_key.get(target_name.lower())
    if not target_key:
        return {"error": f"Unknown target species: {target_name}"}
    implant_passives = canonical_passives(payload.get("implantPassives", []))
    allowed_extras = canonical_passives(payload.get("allowedExtras", []))
    gender_preference = payload.get("genderPreference") or "any"
    target = canonical_passives(payload.get("passives", []))
    if not target:
        return {"error": "Choose the passives you want before calculating perfect IV pairs."}
    if len(target) > 4:
        return {"error": "A Pal can only have 4 final passives."}
    implant_passives &= target
    allowed = allowed_extras | implant_passives
    natural_target = frozenset(target - implant_passives)
    owned = owned_states_for_owner(owner)
    species_states = [s for s in owned if s.species_key == target_key]
    matching = [
        s
        for s in species_states
        if natural_target <= s.passives and not (s.passives - target - allowed)
    ]
    matching_gender = gender_filtered(matching, gender_preference)
    rank_pool = matching_gender or matching
    ranked_matching = sorted(
        rank_pool,
        key=lambda s: (
            -sum(1 for value in (s.avg_hp_iv, s.avg_attack_iv, s.avg_defense_iv) if round(value) >= 100),
            -s.avg_iv,
            s.label,
        ),
    )

    pairs = []
    for a, b in combinations(species_states, 2):
        if not compatible(a, b):
            continue
        if not gender_matches(a, gender_preference) and not gender_matches(b, gender_preference) and gender_preference not in {"", "any", "Any", None}:
            continue
        pool = frozenset(set(a.passives) | set(b.passives))
        missing = natural_target - pool
        junk = pool - target - allowed
        covered, doubled, single, backup = iv_100_score(a, b)
        parent_desired_count = len(a.passives & target) + len(b.passives & target)
        parent_avg = (a.avg_iv + b.avg_iv) / 2
        pairs.append((
            (len(missing), len(junk), -(covered), -(doubled), single, -parent_desired_count, -backup, -parent_avg, a.label, b.label),
            a,
            b,
        ))
    pairs.sort(key=lambda item: item[0])
    serialized_pairs = []
    seen = set()
    for _, a, b in pairs:
        sig = tuple(sorted((a.label, b.label)))
        if sig in seen:
            continue
        seen.add(sig)
        serialized_pairs.append(serialize_iv_pair(a, b, target, natural_target, allowed))
        if len(serialized_pairs) >= 12:
            break

    return {
        "mode": "iv",
        "target": STORE.pals[target_key].name,
        "owner": owner,
        "requestedPassives": sorted(target),
        "naturalPassives": sorted(natural_target),
        "implantPassives": sorted(implant_passives),
        "allowedExtras": sorted(allowed),
        "genderPreference": gender_preference,
        "ivGoal": "perfect",
        "ownedCount": len(owned),
        "targetCount": len(species_states),
        "matchingCount": len(matching),
        "matchingGenderCount": len(matching_gender),
        "matchingPals": [serialize_iv_pal(s, target, allowed) for s in ranked_matching[:24]],
        "pairs": serialized_pairs,
    }


def owned_target_pals_payload(owner: str, target_name: str) -> dict:
    owner_key = (owner or "David").lower()
    target_key = STORE.name_to_key.get((target_name or "").strip().lower())
    if not target_key:
        return {"ok": False, "error": f"Unknown target species: {target_name}"}
    owned = owned_states_for_owner(owner_key)
    species_states = [s for s in owned if s.species_key == target_key]
    target = frozenset()
    allowed = frozenset()
    pals = sorted(
        (serialize_iv_pal(s, target, allowed) for s in species_states),
        key=lambda item: (-len(item["passives"]), -item["avgIv"], item["location"], item["label"]),
    )
    return {
        "ok": True,
        "owner": owner_key,
        "target": STORE.pals[target_key].name,
        "count": len(pals),
        "pals": pals,
    }

def cake_recommendation(target: frozenset[str], iv_preference: str = "none") -> tuple[str, str]:
    if target:
        return "Special Cake", "Best fit when trying to inherit multiple prepared passive skills."
    if iv_preference in {"highest_iv", "highest_attack"}:
        return "Mushroom Cake", "Best fit when the breeding goal is stronger newborn stats."
    return "Cake", "Baseline cake for producing the planned child species."


def opposite_gender(gender: str) -> str:
    if gender == "Male":
        return "Female"
    if gender == "Female":
        return "Male"
    return "any"


def concrete_gender(s: State, intended_gender: str = "any") -> str:
    if intended_gender in {"Male", "Female"}:
        return intended_gender
    if s.gender in {"Male", "Female"}:
        return s.gender
    return "any"


def ordered_parent_specs(a: State, b: State) -> list[tuple[State, str]]:
    a_intended = opposite_gender(concrete_gender(b))
    b_intended = opposite_gender(concrete_gender(a))
    specs = [(a, a_intended), (b, b_intended)]
    order = {"Male": 0, "Female": 1}
    return sorted(specs, key=lambda item: (order.get(concrete_gender(item[0], item[1]), 2), item[0].species, item[0].label))


def serialize_state(s: State, target: frozenset[str], allowed: frozenset[str], intended_gender: str = "any", iv_preference: str = "none") -> dict:
    display_gender = concrete_gender(s, intended_gender)
    if display_gender == "any":
        display_gender = s.gender
    cake_type, cake_reason = cake_recommendation(target, iv_preference)
    parent_items = []
    if s.parents:
        parent_items = [
            serialize_state(parent, target, allowed, parent_intended, iv_preference)
            for parent, parent_intended in ordered_parent_specs(s.parents[0], s.parents[1])
        ]
    location = display_owned_location(s.location)
    return {
        "species": s.species,
        "gender": s.gender,
        "displayGender": display_gender,
        "intendedGender": intended_gender if intended_gender in {"Male", "Female"} else "",
        "steps": s.steps,
        "breedCount": s.breed_count,
        "suggestedCakes": s.breed_count,
        "suggestedCakeType": cake_type if s.breed_count else "",
        "cakeReason": cake_reason if s.breed_count else "",
        "hpIv": round(s.avg_hp_iv, 1),
        "attackIv": round(s.avg_attack_iv, 1),
        "defenseIv": round(s.avg_defense_iv, 1),
        "avgIv": round(s.avg_iv, 1),
        "avgAttackIv": round(s.avg_attack_iv, 1),
        "passives": sorted(s.passives),
        "desired": sorted(s.passives & target),
        "junk": sorted(s.passives - target - allowed),
        "missing": sorted(target - s.passives),
        "allowed": sorted(s.passives & allowed),
        "label": s.label,
        "location": location,
        "box": s.box,
        "slot": s.slot,
        "baseSlot": s.base_slot,
        "icon": icon_url_for_key(s.species_key),
        "types": species_types_for_key(s.species_key),
        "parents": parent_items,
    }




def empty_dps_json() -> dict:
    return {"properties": {"SaveParameterArray": {"value": {"values": []}}}}


def safe_upload_relative_path(name: str) -> Path:
    cleaned = unquote(name or "upload.bin").replace("\\", "/")
    parts = []
    for part in cleaned.split("/"):
        if not part or part in {".", ".."} or ":" in part:
            continue
        parts.append(part)
    return Path(*parts) if parts else Path("upload.bin")


def reset_directory(path: Path) -> None:
    if path.exists():
        def clear_readonly(func, target, _exc_info):
            try:
                os.chmod(target, 0o700)
            except OSError:
                pass
            func(target)
        shutil.rmtree(path, onerror=clear_readonly)
    path.mkdir(parents=True, exist_ok=True)


def multipart_files(content_type: str, body: bytes) -> list[tuple[str, bytes]]:
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;]+))", content_type or "")
    if not match:
        raise ValueError("Missing multipart boundary")
    boundary = (match.group(1) or match.group(2)).encode("utf-8")
    files = []
    for part in body.split(b"--" + boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or part.endswith(b"--") and len(part) == 2:
            continue
        if b"\r\n\r\n" not in part:
            continue
        raw_headers, data = part.split(b"\r\n\r\n", 1)
        headers = raw_headers.decode("latin-1", errors="ignore")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        filename_match = re.search(r'filename="((?:\\"|[^"])*)"', disposition)
        if not filename_match:
            continue
        filename = filename_match.group(1).replace('\\"', '"')
        payload = data.rstrip(b"\r\n")
        rel = safe_upload_relative_path(filename)
        if not rel.suffix and not payload:
            continue
        files.append((filename, payload))
    return files


def save_uploaded_files(files: list[tuple[str, bytes]], stamp: str) -> Path:
    upload_dir = UPLOADS / f"save-{stamp}"
    reset_directory(upload_dir)
    for filename, data in files:
        rel = safe_upload_relative_path(filename)
        dest = (upload_dir / rel).resolve()
        if not str(dest).startswith(str(upload_dir.resolve())):
            continue
        if dest.exists() and dest.is_dir():
            continue
        if not rel.suffix and not data:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return upload_dir


def expand_zip_upload(zip_path: Path, stamp: str) -> Path:
    extract_dir = UPLOADS / f"save-{stamp}-zip"
    reset_directory(extract_dir)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = safe_upload_relative_path(info.filename)
            dest = (extract_dir / rel).resolve()
            if not str(dest).startswith(str(extract_dir.resolve())):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
    return extract_dir


def shortest_file_match(root: Path, predicate) -> Path | None:
    matches = [p for p in root.rglob("*") if p.is_file() and predicate(p)]
    if not matches:
        return None
    return min(matches, key=lambda p: (len(p.relative_to(root).parts), len(str(p))))


def copy_full_save_to_workspace(source_dir: Path, include_dps: bool = True) -> dict:
    reset_directory(WORK)
    if ANALYZER.exists():
        shutil.copy2(ANALYZER, WORK / "analyze_pal_breeding.py")

    level = shortest_file_match(source_dir, lambda p: p.name.lower() == "level.sav")
    if not level:
        return {"ok": False, "error": "No Level.sav found in upload"}
    shutil.copy2(level, WORK / "Level.sav")

    players_dir = WORK / "Players"
    players_dir.mkdir(parents=True, exist_ok=True)
    copied_players = 0
    copied_dps = 0
    save_root = level.parent
    source_players = save_root / "Players"
    candidate_saves = list(source_players.glob("*.sav")) if source_players.exists() else []
    if not candidate_saves:
        candidate_saves = [
            sav for sav in source_dir.rglob("*.sav")
            if "players" in {part.lower() for part in sav.relative_to(source_dir).parts[:-1]} and "backup" not in {part.lower() for part in sav.relative_to(source_dir).parts[:-1]}
        ]
    for sav in sorted(candidate_saves):
        name = sav.name.lower()
        if name == "level.sav":
            continue
        if name.endswith("_dps.sav"):
            if not include_dps:
                continue
            shutil.copy2(sav, players_dir / sav.name)
            copied_dps += 1
        else:
            shutil.copy2(sav, players_dir / sav.name)
            copied_players += 1
    (WORK / "dps.json").write_text(json.dumps(empty_dps_json()), encoding="utf-8")
    return {"ok": True, "level": str(level), "players": copied_players, "dps": copied_dps}


def run_decode_workspace(uploaded_label: str, input_summary: dict | None = None, include_dps: bool = True) -> dict:
    if ANALYZER.exists():
        shutil.copy2(ANALYZER, WORK / "analyze_pal_breeding.py")
    (WORK / "dps.json").write_text(json.dumps(empty_dps_json()), encoding="utf-8")

    setup_error = decoder_setup_error()
    if setup_error:
        return {
            "ok": False,
            "error": "Decoder setup incomplete",
            "errorDetail": setup_error,
        }

    w_work = wsl_path(WORK)
    w_tools = wsl_path(TOOLS)
    commands = [
        f"cd {w_tools}",
        ". .wsl-venv/bin/activate",
        f"export PALWORLD_PARSER_ASSETS_DIR={w_tools}/palworld-server-tool/web/src/assets",
        f"python3 palworld-server-tool/sav_cli/sav_cli.py -f {w_work}/Level.sav -o {w_work}/structure.json",
        f"palsav convert {w_work}/Level.sav --to-json -o {w_work}/Level.full.json --force",
    ]
    players_dir = WORK / "Players"
    if players_dir.exists():
        for sav in sorted(players_dir.glob("*.sav")):
            if sav.name.lower().endswith("_dps.sav"):
                continue
            commands.append(f'palsav convert "{wsl_path(sav)}" --to-json -o "{wsl_path(sav.with_suffix(".json"))}" --force')
        dps_savs = sorted(players_dir.glob("*_dps.sav")) if include_dps else []
        if dps_savs:
            commands.append(f'palsav convert "{wsl_path(dps_savs[0])}" --to-json -o {w_work}/dps.decoded.json --force && mv {w_work}/dps.decoded.json {w_work}/dps.json || echo "WARN: DPS decode failed for {dps_savs[0].name}; continuing with empty DPS"')
    commands.extend([
        f"cd {w_work}",
        "python3 analyze_pal_breeding.py",
    ])
    command = " && ".join(commands)
    proc = subprocess.run(
        ["wsl", "bash", "-lc", command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=300,
    )
    if proc.returncode != 0:
        detail = decode_failure_detail(proc.stdout, proc.stderr)
        return {
            "ok": False,
            "error": "Decode failed",
            "errorDetail": detail,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
            "returnCode": proc.returncode,
        }

    copied = []
    for src_name, dest in [
        ("pal_roster.csv", DATA_ROOT / "pal_roster.csv"),
        ("passive_inventory.csv", DATA_ROOT / "passive_inventory.csv"),
        ("breeding_report.md", REPORTS_ROOT / "breeding_report.md"),
    ]:
        src = WORK / src_name
        if src.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied.append(str(dest.relative_to(ROOT)))

    STORE.reload()
    BASE_WORK_CACHE["payload"] = None
    BASE_WORK_CACHE["mtime"] = None
    return {
        "ok": True,
        "uploaded": uploaded_label,
        "input": input_summary or {},
        "copied": copied,
        "rosterCount": len(STORE.roster),
        "owners": STORE.owners,
        "stdout": proc.stdout[-2000:],
    }


def decoder_setup_error() -> str | None:
    required = [
        TOOLS / ".wsl-venv" / "bin" / "activate",
        TOOLS / "palworld-server-tool" / "sav_cli" / "sav_cli.py",
        TOOLS / "PalSav" / "pyproject.toml",
    ]
    missing = []
    for path in required:
        try:
            exists = path.exists()
        except OSError:
            exists = False
        if not exists:
            missing.append(path)
    if not missing:
        try:
            proc = subprocess.run(
                ["wsl", "bash", "-lc", f"cd {wsl_path(TOOLS)} && test -x .wsl-venv/bin/python3"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return f"unable to verify WSL parser Python; rebuild parser tools with the WSL venv setup command in README.md ({exc})"
        if proc.returncode == 0:
            return None
        detail = decode_failure_detail(proc.stdout, proc.stderr)
        return f"missing {TOOLS / '.wsl-venv' / 'bin' / 'python3'}; rebuild parser tools with the WSL venv setup command in README.md ({detail})"
    first = missing[0]
    return f"missing {first}; rebuild parser tools with the WSL venv setup command in README.md"


def decode_failure_detail(stdout: str, stderr: str) -> str:
    lines = []
    for text in (stderr, stdout):
        for line in text.splitlines():
            line = line.strip()
            if line:
                lines.append(line)
    if not lines:
        return "decoder exited without output"

    interesting = [
        line for line in lines
        if (
            "error" in line.lower()
            or "failed" in line.lower()
            or "traceback" in line.lower()
            or "not found" in line.lower()
            or "no such file" in line.lower()
            or "command not found" in line.lower()
        )
    ]
    chosen = interesting[-1] if interesting else lines[-1]
    return chosen[-500:]


def run_decode_from_save_dir(source_dir: Path, uploaded_label: str, include_dps: bool = True) -> dict:
    prepared = copy_full_save_to_workspace(source_dir, include_dps=include_dps)
    if not prepared.get("ok"):
        return prepared
    prepared["dpsSkipped"] = not include_dps
    return run_decode_workspace(uploaded_label, prepared, include_dps=include_dps)

def wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = resolved.as_posix()[3:]
    return f"/mnt/{drive}/{rest}"


def run_decode_from_level(upload_path: Path) -> dict:
    if not upload_path.exists():
        return {"ok": False, "error": f"Upload not found: {upload_path}"}
    WORK.mkdir(parents=True, exist_ok=True)
    shutil.copy2(upload_path, WORK / "Level.sav")
    return run_decode_workspace(str(upload_path.relative_to(ROOT)), {"levelOnly": True})


def live_save_files() -> list[Path]:
    if LIVE_SAVE_DIR is None:
        return []
    if not LIVE_SAVE_DIR.exists():
        return []
    files: list[Path] = []
    level = LIVE_SAVE_DIR / "Level.sav"
    if level.is_file():
        files.append(level)
    players = LIVE_SAVE_DIR / "Players"
    if players.exists():
        files.extend(sorted(p for p in players.glob("*.sav") if p.is_file()))
    return files


def live_save_fingerprint() -> tuple[str, int, float]:
    entries = []
    latest_modified = 0.0
    for file_path in live_save_files():
        try:
            stat = file_path.stat()
        except OSError:
            continue
        latest_modified = max(latest_modified, stat.st_mtime)
        rel = file_path.relative_to(LIVE_SAVE_DIR).as_posix() if LIVE_SAVE_DIR is not None else file_path.name
        entries.append(f"{rel}:{stat.st_size}:{stat.st_mtime_ns}")
    return "|".join(sorted(entries)), len(entries), latest_modified


def persist_live_state() -> None:
    LIVE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIVE_STATE_FILE.write_text(json.dumps(LIVE_STATE, indent=2), encoding="utf-8")


def live_save_status() -> dict:
    if LIVE_SAVE_DIR is None:
        return {
            "ok": False,
            "configured": False,
            "path": "",
            "exists": False,
            "levelExists": False,
            "fingerprint": "",
            "fileCount": 0,
            "latestModified": 0.0,
            "lastRefreshFingerprint": LIVE_STATE["last_refresh_fingerprint"],
            "lastRefreshAt": LIVE_STATE["last_refresh_at"],
            "refreshing": LIVE_LOCK.locked(),
            "lastResult": LIVE_STATE["last_result"],
        }
    exists = LIVE_SAVE_DIR.exists()
    level_exists = (LIVE_SAVE_DIR / "Level.sav").is_file()
    fingerprint, file_count, latest_modified = live_save_fingerprint() if exists else ("", 0, 0.0)
    return {
        "ok": exists and level_exists,
        "configured": True,
        "path": str(LIVE_SAVE_DIR),
        "exists": exists,
        "levelExists": level_exists,
        "fingerprint": fingerprint,
        "fileCount": file_count,
        "latestModified": latest_modified,
        "lastRefreshFingerprint": LIVE_STATE["last_refresh_fingerprint"],
        "lastRefreshAt": LIVE_STATE["last_refresh_at"],
        "refreshing": LIVE_LOCK.locked(),
        "lastResult": LIVE_STATE["last_result"],
    }


def refresh_live_save(force: bool = False) -> dict:
    if LIVE_SAVE_DIR is None:
        status = live_save_status()
        status.update({"ok": False, "refreshing": False, "error": "PALWORLD_LIVE_SAVE_DIR is not configured."})
        return status
    if not LIVE_LOCK.acquire(blocking=False):
        status = live_save_status()
        status.update({"ok": False, "refreshing": True, "error": "Live save refresh already running"})
        return status
    try:
        before = live_save_status()
        if not before["ok"]:
            before.update({"ok": False, "refreshing": False, "error": "Live save folder or Level.sav was not found"})
            return before
        if not force:
            before.update({"ok": True, "refreshing": False, "skipped": True, "message": "Auto refresh is disabled. Use Sync Save to refresh manually."})
            return before
        if before["fingerprint"] == LIVE_STATE["last_refresh_fingerprint"]:
            before.update({"ok": True, "refreshing": False, "skipped": True, "message": "Live save is already current"})
            return before
        result = run_decode_from_save_dir(LIVE_SAVE_DIR, "live-save", include_dps=False)
        after = live_save_status()
        after["refreshing"] = False
        if result.get("ok"):
            LIVE_STATE["last_refresh_fingerprint"] = after["fingerprint"]
            LIVE_STATE["last_refresh_at"] = datetime.now().isoformat(timespec="seconds")
        LIVE_STATE["last_result"] = {
            "ok": bool(result.get("ok")),
            "rosterCount": result.get("rosterCount"),
            "error": result.get("error"),
            "errorDetail": result.get("errorDetail"),
            "at": datetime.now().isoformat(timespec="seconds"),
        }
        if result.get("ok"):
            persist_live_state()
        result["live"] = {**after, "lastRefreshFingerprint": LIVE_STATE["last_refresh_fingerprint"], "lastRefreshAt": LIVE_STATE["last_refresh_at"], "lastResult": LIVE_STATE["last_result"]}
        return result
    finally:
        LIVE_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/options":
            self.send_json({
                "species": STORE.species_names,
                "passives": STORE.passives,
                "passivesByOwner": STORE.passives_by_owner,
                "passiveMeta": STORE.passive_meta,
                "speciesMeta": species_meta(),
                "owners": STORE.owners,
                "workTypes": [{"key": key, "label": label} for key, label in sorted(WORK_LABELS.items(), key=lambda item: item[1])],
                "baseSites": base_work_sites_payload(),
                "implantInventory": load_implant_inventory(),
                "rosterCount": len(STORE.roster),
                "dataVersion": STORE.breeding_data.get("dataVersion"),
                "generatedAt": STORE.breeding_data.get("generatedAt"),
            })
            return
        if path == "/api/work-suitability":
            query = parse_qs(urlparse(self.path).query)
            owner = query.get("owner", [""])[0]
            work = query.get("work", [""])[0]
            self.send_json(work_suitability_payload(owner=owner, selected_work=work))
            return
        if path == "/api/ranch-drops":
            query = parse_qs(urlparse(self.path).query)
            owner = query.get("owner", [""])[0]
            self.send_json(ranch_drops_payload(owner=owner))
            return
        if path == "/api/base-work-sites":
            self.send_json(base_work_sites_payload())
            return
        if path == "/api/owned-target-pals":
            query = parse_qs(urlparse(self.path).query)
            owner = query.get("owner", ["David"])[0]
            target = query.get("target", [""])[0]
            self.send_json(owned_target_pals_payload(owner, target))
            return
        if path == "/api/reload":
            STORE.reload()
            BASE_WORK_CACHE["payload"] = None
            BASE_WORK_CACHE["mtime"] = None
            self.send_json({"ok": True, "rosterCount": len(STORE.roster)})
            return
        if path == "/api/live-save/status":
            self.send_json(live_save_status())
            return
        if path.startswith("/assets/pals/"):
            name = Path(path).name
            file_path = (PAL_IMAGES / name).resolve()
            if not str(file_path).startswith(str(PAL_IMAGES.resolve())) or not file_path.exists():
                self.send_error(404)
                return
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/":
            path = "/index.html"
        file_path = (WEB / path.lstrip("/")).resolve()
        if not str(file_path).startswith(str(WEB.resolve())) or not file_path.exists():
            self.send_error(404)
            return
        content_type = "text/html"
        if file_path.suffix == ".css":
            content_type = "text/css"
        elif file_path.suffix == ".js":
            content_type = "application/javascript"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        length = as_int(self.headers.get("Content-Length"))
        body = self.rfile.read(length) if length else b""
        if path == "/api/upload-save":
            if not body:
                self.send_json({"ok": False, "error": "No file data received"}, status=400)
                return
            UPLOADS.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            content_type = self.headers.get("Content-Type", "")
            try:
                files = multipart_files(content_type, body) if content_type.startswith("multipart/form-data") else []
                if not files:
                    filename = self.headers.get("X-Filename", "Level.sav")
                    files = [(filename, body)]
                upload_dir = save_uploaded_files(files, stamp)
                uploaded_files = [p for p in upload_dir.rglob("*") if p.is_file()]
                if len(uploaded_files) == 1 and uploaded_files[0].suffix.lower() == ".zip":
                    upload_dir = expand_zip_upload(uploaded_files[0], stamp)
                self.send_json(run_decode_from_save_dir(upload_dir, str(upload_dir.relative_to(ROOT))))
            except zipfile.BadZipFile:
                self.send_json({"ok": False, "error": "Uploaded .zip is not a valid zip file"}, status=400)
            except Exception as exc:
                self.send_json({"ok": False, "error": str(exc)}, status=500)
            return
        if path == "/api/upload-level":
            if not body:
                self.send_json({"ok": False, "error": "No file data received"}, status=400)
                return
            UPLOADS.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            upload_path = UPLOADS / f"Level-{stamp}.sav"
            upload_path.write_bytes(body)
            self.send_json(run_decode_from_level(upload_path))
            return
        payload = json.loads(body or b"{}")
        if path == "/api/live-save/refresh":
            result = refresh_live_save(force=bool(payload.get("force")))
            self.send_json(result, 409 if result.get("refreshing") and not result.get("ok") else 200)
            return
        if path == "/api/optimize":
            self.send_json(build_plan(payload))
            return
        if path == "/api/profile-passives":
            result = profile_passives_payload(payload)
            self.send_json(result, 400 if not result.get("ok") else 200)
            return
        if path == "/api/improve-ivs":
            self.send_json(build_iv_plan(payload))
            return
        if path == "/api/base-labels":
            labels = load_base_labels()
            base_id = str(payload.get("baseId") or "")
            label = str(payload.get("label") or "").strip()
            if not base_id:
                self.send_json({"ok": False, "error": "Missing baseId"}, status=400)
                return
            if label:
                labels[base_id] = label[:80]
            else:
                labels.pop(base_id, None)
            save_base_labels(labels)
            BASE_WORK_CACHE["payload"] = None
            self.send_json({"ok": True, "labels": labels})
            return
        if path == "/api/implant-inventory":
            inventory = load_implant_inventory()
            passive = str(payload.get("passive") or "").strip()
            if not passive:
                self.send_json({"ok": False, "error": "Missing passive"}, status=400)
                return
            if payload.get("delete"):
                inventory.pop(passive, None)
            else:
                infinite = bool(payload.get("infinite"))
                count = max(0, as_int(payload.get("count")))
                inventory[passive] = {"infinite": infinite, "count": None if infinite else count}
            save_implant_inventory(inventory)
            self.send_json({"ok": True, "inventory": inventory})
            return
        if path == "/api/base-planner":
            self.send_json(build_base_planner(payload))
            return
        self.send_error(404)


def start_startup_live_sync() -> None:
    def worker():
        print("Startup sync: checking live save...")
        try:
            result = refresh_live_save(force=True)
        except Exception as exc:
            print(f"Startup sync failed: {exc}")
            return
        if result.get("skipped"):
            print(f"Startup sync skipped: {result.get('message', 'live save already current')}")
        elif result.get("ok"):
            print(f"Startup sync complete: {result.get('rosterCount')} rows loaded")
        else:
            print(f"Startup sync failed: {result.get('error', 'unknown error')}")
            if result.get("errorDetail"):
                print(f"Startup sync detail: {result.get('errorDetail')}")

    threading.Thread(target=worker, name="startup-live-save-sync", daemon=True).start()


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Palworld Breeding Optimizer GUI: http://127.0.0.1:8765")
    print("Press Ctrl+C to stop.")
    start_startup_live_sync()
    server.serve_forever()


if __name__ == "__main__":
    main()
