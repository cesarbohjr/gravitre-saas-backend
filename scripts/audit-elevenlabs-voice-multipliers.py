"""Audit curated preset voice_ids for ElevenLabs credit multipliers.

Uses local ELEVENLABS_API_KEY when present; otherwise prints the voice id list
and exits non-zero so prod /library/multiplier-audit can be used.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

for candidate in [ROOT / "backend" / ".env.operator.local", ROOT / "backend" / ".env"]:
    if not candidate.exists():
        continue
    for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value

from app.config import get_settings  # noqa: E402
from app.services.voice_library_service import (  # noqa: E402
    CURATED_VOICE_META,
    audit_curated_voice_multipliers,
)


def main() -> int:
    settings = get_settings()
    if not (settings.elevenlabs_api_key or "").strip():
        print(
            json.dumps(
                {
                    "error": "ELEVENLABS_API_KEY unset locally",
                    "curated_voice_ids": list(CURATED_VOICE_META.keys()),
                    "failed_prove_voice_id": "21m00Tcm4TlvDq8ikWAM",
                    "next": "Call GET /api/voice/library/multiplier-audit on prod with addon",
                },
                indent=2,
            )
        )
        return 2
    report = audit_curated_voice_multipliers(settings)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
