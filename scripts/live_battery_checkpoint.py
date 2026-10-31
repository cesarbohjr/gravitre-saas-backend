"""Keep incomplete live-battery evidence without upgrading it to a pass."""
import json
from pathlib import Path


def checkpoint(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A timeout can interrupt any later request/poll. Atomically retain the
    # last complete observation; the controller must still reject RUNNING.
    partial = {**report, "verdict": "RUNNING"}
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(partial, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
