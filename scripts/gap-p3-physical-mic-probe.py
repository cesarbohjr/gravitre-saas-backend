#!/usr/bin/env python3
"""Authorized physical-microphone attempt. Never manufacture HUMAN_EXPERIENCE_PENDING."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "audits" / "gravitre-p3-physical-mic-live.json"


def _list_windows_capture_devices() -> list[str]:
    names: list[str] = []
    try:
        import subprocess

        raw = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-PnpDevice -Class AudioEndpoint -Status OK -ErrorAction SilentlyContinue "
                "| Select-Object -ExpandProperty FriendlyName",
            ],
            text=True,
            timeout=20,
        )
        names = [line.strip() for line in raw.splitlines() if line.strip()]
    except Exception as exc:  # noqa: BLE001
        names = [f"enumeration_error:{exc.__class__.__name__}"]
    return names


def main() -> int:
    devices = _list_windows_capture_devices()
    capture_like = [
        n
        for n in devices
        if n
        and "enumeration_error" not in n.lower()
        and any(tok in n.lower() for tok in ("mic", "microphone", "array", "headset"))
    ]
    can_run_human = bool(capture_like) and sys.stdin.isatty()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audio_endpoints_ok": devices[:20],
        "capture_like": capture_like[:10],
        "stdin_is_tty": bool(sys.stdin.isatty()),
        "used_physical_microphone": False,
        "human_spoken_turns": 0,
        "barge_in_observed": False,
        "correction_observed": False,
        "approval_language_spoken": False,
        "verdict": "HUMAN_EXPERIENCE_PENDING",
        "reason": (
            "This agent session has no authorized human speaker driving a live microphone "
            "through the production voice UI. Synthetic PCM remains separately proven. "
            "Physical-mic conversational acceptance is not manufactured."
            if not can_run_human
            else "Capture device present, but this run is not an attended human conversation."
        ),
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
