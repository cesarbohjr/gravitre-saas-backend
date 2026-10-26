"""Offline coverage for the Railway deletion go-live readiness collector."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_deletion_lifecycle_readiness.py"
spec = importlib.util.spec_from_file_location("readiness_check", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _report(**overrides):
    data = {
        "lifecycle_ready": True, "missing": [],
        "runtime": {"ready": True, "blockers": [], "relay_task": "running",
                    "heartbeat_age_s": 3, "heartbeat_window_s": 60},
    }
    data.update(overrides)
    return SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")


@pytest.mark.parametrize("result,expected", [
    (_report(), 0),
    (_report(lifecycle_ready=False, missing=["SOURCE_DELETION_PROPAGATION_ENABLED"]), 1),
    (_report(runtime={"ready": False, "blockers": ["relay_task_exited"],
                      "relay_task": "exited", "heartbeat_age_s": 3, "heartbeat_window_s": 60}), 1),
    (_report(runtime={"ready": True, "blockers": [], "relay_task": "running",
                      "heartbeat_age_s": 60, "heartbeat_window_s": 60}), 1),
    (SimpleNamespace(returncode=22, stdout="not JSON", stderr="secret should never print"), 1),
])
def test_offline_samples(result, expected, capsys):
    with patch("sys.argv", ["check", "--replicas", "1", "--calls", "2", "--delay", "0"]), \
         patch.object(mod.subprocess, "run", return_value=result), \
         patch.object(mod.time, "sleep"):
        assert mod.main() == expected
    text = capsys.readouterr().out
    assert "secret should never print" not in text
    payload = json.loads(text[text.index("{"):])
    assert payload["calls"] == 2
    assert payload["result"] == ("PASS" if expected == 0 else "FAIL")
    assert payload["lifecycle_ready_true"] == (2 if expected == 0 else 0)


def test_rejects_insufficient_replica_sampling():
    with patch("sys.argv", ["check", "--replicas", "5", "--calls", "8"]):
        with pytest.raises(SystemExit) as exc:
            mod.main()
    assert exc.value.code == 2
