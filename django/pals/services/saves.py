"""Save import, decode, and live-sync helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import zipfile
from datetime import datetime
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from urllib.parse import unquote

from .data import (
    ANALYZER,
    DATA_ROOT,
    LIVE_LOCK,
    LIVE_SAVE_DIR,
    LIVE_STATE,
    LIVE_STATE_FILE,
    REPORTS_ROOT,
    ROOT,
    STORE,
    TOOLS,
    UPLOADS,
    WORK,
)

_refresh_hooks = []


def register_refresh_hook(callback) -> None:
    _refresh_hooks.append(callback)


def invalidate_refresh_dependents() -> None:
    for callback in list(_refresh_hooks):
        callback()


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
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    if not message.is_multipart():
        raise ValueError("Invalid multipart upload or missing boundary")
    files = []
    for part in message.iter_parts():
        filename = part.get_filename()
        if filename is None:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
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
    invalidate_refresh_dependents()
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


def live_sync_available() -> bool:
    return LIVE_SAVE_DIR is not None


def module_status() -> dict[str, str]:
    if LIVE_SAVE_DIR is None:
        return {"state": "opt_in", "message": "Save sync will stay disabled until explicitly configured."}
    return {"state": "ready", "message": "Save import and live sync helpers are available."}
