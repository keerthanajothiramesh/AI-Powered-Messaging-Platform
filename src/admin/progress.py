"""In-memory progress tracker for demo seeding — exposes step/count state to the admin status endpoint."""
from typing import Any, Dict

_INITIAL: Dict[str, Any] = {
    "status": "idle",
    "step": "",
    "users_loaded": 0, "users_total": 0,
    "groups_loaded": 0, "groups_total": 0,
    "messages_loaded": 0, "messages_total": 0,
    "embeddings_loaded": 0, "embeddings_total": 0,
    "error": None,
}

_progress: Dict[str, Any] = dict(_INITIAL)


def get_progress() -> Dict[str, Any]:
    return dict(_progress)


def reset_progress(status: str = "running") -> None:
    global _progress
    _progress = {**_INITIAL, "status": status}


def set_status(status: str, step: str = "", error: str = None) -> None:
    _progress["status"] = status
    _progress["step"] = step
    if error is not None:
        _progress["error"] = error


def set_step(step: str) -> None:
    _progress["step"] = step


def increment(key: str, amount: int = 1) -> None:
    _progress[key] = _progress.get(key, 0) + amount


def set_total(key: str, total: int) -> None:
    _progress[key] = total
