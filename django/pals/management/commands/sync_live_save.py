import time

from django.core.management.base import BaseCommand

from pals.services import saves


class Command(BaseCommand):
    help = "Poll the configured live save and decode it when its fingerprint changes."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=30)
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        interval = max(5, options["interval"])
        while True:
            result = saves.refresh_live_save(force=True)
            if result.get("error") or (result.get("ok") and not result.get("skipped")):
                self.stdout.write(str(result.get("message") or result.get("error") or "Live save synced"))
            if options["once"]:
                return
            time.sleep(interval)
