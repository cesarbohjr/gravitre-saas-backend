"""CI: chat/TTS stream writes may only run inside the Response Composer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scan_response_composer_bypass.py"

DISPOSABLE_DIRECT_WRITE = '''
def evil_direct_stream_write(text_id: str, payload: str):
    from app.operators.assistant_sse import sse_text_delta
    yield sse_text_delta(text_id, payload)
'''


def test_no_direct_stream_writes_outside_the_composer() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_disposable_direct_write_fails_the_scan() -> None:
    """Deliberate disposable attempt: a new yield sse_text_delta outside the Composer."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from scan_response_composer_bypass import scan_source

    hits = scan_source(DISPOSABLE_DIRECT_WRITE, path="evil_stream_write.py")
    assert hits, "scanner must fail a direct stream write, not pass vacuously"
    assert any(name == "sse_text_delta" for _, _, name in hits)
