"""CI: canned shortcut producers may only run inside the Intent Gateway."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scan_intent_gateway_bypass.py"

THIRTEENTH_SHORTCUT = '''
def evil_thirteenth_shortcut(message: str) -> str | None:
    from app.services.frontend_ia_nav_faq import match_frontend_ia_nav_faq
    hit = match_frontend_ia_nav_faq(message)
    if hit:
        return hit["answer"]
    return None
'''


def test_no_candidate_producers_outside_the_gateway() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_a_thirteenth_shortcut_outside_the_gateway_fails_the_scan() -> None:
    """Deliberate disposable attempt: a new FAQ return outside the gateway."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from scan_intent_gateway_bypass import scan_source

    hits = scan_source(THIRTEENTH_SHORTCUT, path="evil_shortcut.py")
    assert hits, "scanner must fail a thirteenth shortcut, not pass vacuously"
    assert any(name == "match_frontend_ia_nav_faq" for _, _, name in hits)
