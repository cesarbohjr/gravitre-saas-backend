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


def test_exemption_cannot_be_claimed_by_renaming_a_file(tmp_path: Path) -> None:
    """The exemption is a path, not a name.

    scan_source above proves the detector fires, but it never consults the
    exemption set, so it could not see this: while exemptions matched on
    basename, a disposable probe at routers/response_composer.py holding an
    identical direct write scanned clean against the real tree. Exercise
    scan_app, which is the function CI actually calls.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from scan_response_composer_bypass import scan_app

    (tmp_path / "services").mkdir()
    (tmp_path / "routers").mkdir()
    # The real Composer: genuinely exempt, writes freely.
    (tmp_path / "services" / "response_composer.py").write_text(
        DISPOSABLE_DIRECT_WRITE, encoding="utf-8"
    )
    # An impostor that only shares the basename.
    (tmp_path / "routers" / "response_composer.py").write_text(
        DISPOSABLE_DIRECT_WRITE, encoding="utf-8"
    )

    hits = scan_app(tmp_path)
    caught = {path for path, _, _ in hits}
    assert "routers/response_composer.py" in caught, (
        "a file that merely adopts an exempt basename must not inherit the exemption"
    )
    assert "services/response_composer.py" not in caught, (
        "the real Composer must stay exempt"
    )
