"""Single place that removes files from disk — always via the OS Recycle Bin."""
from pathlib import Path


def move_to_trash(paths: list[str]) -> tuple[list[str], list[dict]]:
    """Send each path to the Recycle Bin. Returns (succeeded, [{path, error}])."""
    from send2trash import send2trash

    ok: list[str] = []
    errors: list[dict] = []
    for p in paths:
        try:
            if Path(p).exists():
                send2trash(p)
            ok.append(p)
        except Exception as e:  # noqa: BLE001
            errors.append({"path": p, "error": str(e)})
    return ok, errors
