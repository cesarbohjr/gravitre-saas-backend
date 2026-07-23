#!/usr/bin/env python3
"""Classify Gravitree tests by pyramid layer (unit / integration / live-prod battery).

Writes JSON for delivery tracking — does not run tests.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_TESTS = ROOT / "backend" / "tests"
APPS_WEB_TESTS = ROOT / "apps" / "web" / "__tests__"
E2E = ROOT / "e2e"
SCRIPTS = ROOT / "scripts"

LIVE_BATTERY_RE = re.compile(
    r"verify-unified-turn|smoke-.*-live|battery.*live|oauth-smoke-live|chat-e2e.*live",
    re.I,
)
INTEGRATION_MARKERS = (
    "integration",
    "test_integration",
    "smoke-",
    "e2e",
)


@dataclass
class LayerCounts:
    unit_backend_pytest: int = 0
    unit_web_vitest: int = 0
    integration_backend_pytest: int = 0
    playwright_e2e: int = 0
    live_prod_battery_scripts: int = 0


@dataclass
class PyramidReport:
    generated_from: str = str(ROOT)
    layers: LayerCounts = field(default_factory=LayerCounts)
    live_battery_scripts: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def total_automated_local(self) -> int:
        l = self.layers
        return l.unit_backend_pytest + l.unit_web_vitest + l.integration_backend_pytest + l.playwright_e2e

    @property
    def inverted_pyramid_signal(self) -> bool:
        """Heuristic: live batteries carry disproportionate verification weight vs cheap unit count."""
        l = self.layers
        if l.live_prod_battery_scripts < 5:
            return False
        unit = l.unit_backend_pytest + l.unit_web_vitest
        return l.live_prod_battery_scripts * 50 > unit  # ~50:1 script:unit threshold for flag


def _count_pytest_files(directory: Path, *, integration: bool) -> int:
    if not directory.is_dir():
        return 0
    n = 0
    for path in directory.rglob("test_*.py"):
        rel = path.relative_to(directory).as_posix().lower()
        is_int = any(m in rel for m in INTEGRATION_MARKERS)
        if integration and is_int:
            n += 1
        elif not integration and not is_int:
            n += 1
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path", help="Write report JSON")
    args = parser.parse_args()

    report = PyramidReport()
    report.layers.unit_backend_pytest = _count_pytest_files(BACKEND_TESTS, integration=False)
    report.layers.integration_backend_pytest = _count_pytest_files(BACKEND_TESTS, integration=True)
    if APPS_WEB_TESTS.is_dir():
        report.layers.unit_web_vitest = len(list(APPS_WEB_TESTS.rglob("*.test.ts")))
    report.layers.unit_web_vitest += len(list((ROOT / "apps" / "web" / "lib").rglob("*.test.ts")))
    if E2E.is_dir():
        report.layers.playwright_e2e = len(list(E2E.rglob("*.spec.ts")))

    for path in sorted(SCRIPTS.glob("*.py")):
        name = path.name
        if LIVE_BATTERY_RE.search(name):
            report.live_battery_scripts.append(name)
    report.layers.live_prod_battery_scripts = len(report.live_battery_scripts)

    report.notes.append(
        "Live-prod batteries are manual/scheduled workflows — they do not replace unit tests; "
        "they validate prod paths pytest cannot reach."
    )
    if report.inverted_pyramid_signal:
        report.notes.append(
            "INVERTED_PYRAMID_SIGNAL: many live battery scripts vs unit file count — "
            "prioritize shifting verification left (mapper/unified-turn contract tests)."
        )

    payload = {
        **asdict(report),
        "total_automated_local_files": report.total_automated_local,
        "inverted_pyramid_signal": report.inverted_pyramid_signal,
    }
    text = json.dumps(payload, indent=2)
    print(text)
    if args.json_path:
        out = Path(args.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
