"""Save import and sync service placeholders."""


def live_sync_available() -> bool:
    return False


def module_status() -> dict[str, str]:
    return {"state": "opt_in", "message": "Save sync will stay disabled until explicitly configured."}
