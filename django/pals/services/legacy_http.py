"""Optional legacy standalone HTTP adapter; Django uses pals.views."""

from __future__ import annotations

import json
import threading
import zipfile

from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .bases import (
    BASE_WORK_CACHE,
    base_work_sites_payload,
    build_base_planner,
    load_base_labels,
    save_base_labels,
)
from .breeding import build_plan, profile_passives_payload
from .data import PAL_IMAGES, ROOT, STORE, UPLOADS, WEB, WORK_LABELS, as_int
from .ivs import (
    build_iv_plan,
    load_implant_inventory,
    owned_target_pals_payload,
    save_implant_inventory,
)
from .ranch import ranch_drops_payload
from .saves import (
    expand_zip_upload,
    live_save_status,
    multipart_files,
    refresh_live_save,
    run_decode_from_level,
    run_decode_from_save_dir,
    save_uploaded_files,
)
from .work import species_meta, work_suitability_payload


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
