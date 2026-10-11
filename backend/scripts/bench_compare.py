#!/usr/bin/env python3
"""Benchmark two git revisions under identical conditions and compare them.

Each revision is checked out with ``git worktree add`` into a temporary
directory (the head may instead be the current checkout, uncommitted edits
included). By default the bench driver of the current checkout (the bench
scripts, ``scripts/bench_profiles`` and ``tests/e2e/voice_scenarios``) is
copied over each checkout, so both sides run the same scenarios, metrics and
grading against their own product code; ``--revision-harness`` keeps each
revision's own copy instead. Both sides then run with the same Python, profile,
seed and N, one after the other, and a comparison is written.

Run from ``backend/``::

    python scripts/bench_compare.py --base a7719cba --head WORKTREE \\
        --profile production_inferred --runs 20 --seed 1000 --chat-runs 15 \\
        --out /tmp/bench/compare

Writes ``<out>/<side>/voice/results.{json,md}``, ``<out>/<side>/chat/results.{json,md}``
(with ``--chat-runs``) and ``<out>/comparison.md``.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CURRENT = "WORKTREE"
# The bench driver: identical on both sides unless --revision-harness.
HARNESS_PATHS = (
    "scripts/bench_voice_scenarios.py",
    "scripts/bench_chat_turns.py",
    "scripts/bench_profiles",
    "tests/e2e/voice_scenarios",
)
BENCH_ENV = {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "anon-test",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-test",
    "SUPABASE_JWT_SECRET": "jwt-secret-test",
    "OPENAI_API_KEY": "sk-test-openai",
    "GRAVITRE_DROP_BACKGROUND_TASKS": "1",
}


def _git(*args: str, cwd: Path = BACKEND_ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _checkout(rev: str, tmp: Path, side: str) -> tuple[Path, bool]:
    """backend/ dir for ``rev`` and whether it is a temporary worktree."""
    if rev == CURRENT:
        return BACKEND_ROOT, False
    path = tmp / side
    subprocess.check_call(["git", "worktree", "add", "--detach", str(path), rev], cwd=BACKEND_ROOT)
    return path / "backend", True


def _overlay_harness(dest_backend: Path) -> None:
    if dest_backend.resolve() == BACKEND_ROOT.resolve():
        return
    for rel in HARNESS_PATHS:
        src, dst = BACKEND_ROOT / rel, dest_backend / rel
        if src.is_dir():
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        elif src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def _run(cmd: list[str], cwd: Path, log: Path) -> None:
    env = dict(os.environ)
    for key, value in BENCH_ENV.items():
        env.setdefault(key, value)
    log.parent.mkdir(parents=True, exist_ok=True)
    print(f"$ (cd {cwd} && {' '.join(cmd)})  > {log}", flush=True)
    with log.open("w") as fh:
        proc = subprocess.run(cmd, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"bench failed ({proc.returncode}); see {log}")


def _load(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text()) if path.exists() else None


def _p(stat: dict[str, Any] | None, key: str = "p50") -> str:
    if not stat or not stat.get("n") or stat.get(key) is None:
        return "–"
    return f"{stat[key]:.0f}"


def _delta(a: dict[str, Any] | None, b: dict[str, Any] | None, key: str = "p50") -> str:
    if not a or not b or a.get(key) is None or b.get(key) is None:
        return ""
    d = b[key] - a[key]
    return f" ({d:+.0f})" if abs(d) >= 0.5 else " (=)"


def _acc(stat: dict[str, Any] | None) -> str:
    return f"{stat['pass']}/{stat['n']}" if stat and stat.get("n") else "–"


def comparison_markdown(sides: dict[str, dict[str, Any]], args: argparse.Namespace) -> str:
    base, head = sides["base"], sides["head"]
    lines = [
        "# Bench comparison",
        "",
        "| | base | head |",
        "|---|---|---|",
        f"| revision | {base['rev']} | {head['rev']} |",
        f"| commit | {base.get('commit') or '–'} | {head.get('commit') or '–'} |",
        f"| backend/app tree | {base.get('app_tree') or '–'} | {head.get('app_tree') or '–'} |",
        f"| harness | {base['harness']} | {head['harness']} |",
        "",
        (
            f"Profile **{args.profile or '(none)'}** · runs per scenario {args.runs} · seed base {args.seed} · "
            f"chat samples per turn {args.chat_runs or 'not run'} · same Python ({sys.version.split()[0]}) "
            "on one host, base first."
        ),
        "",
    ]
    if base.get("app_tree") and base.get("app_tree") == head.get("app_tree"):
        lines += ["Note: both sides have the same backend/app tree (no product change); differences are noise or harness changes.", ""]
    bv, hv = base.get("voice"), head.get("voice")
    if bv and hv:
        lines += [
            "## Voice scenarios (virtual clock: deterministic per seed)",
            "",
            "Cells are base → head P50 in ms (delta); accuracy is passing runs / graded runs.",
            "",
            "| Scenario | accuracy | first useful audible (answer) | first audio (any) | barge-in → quiet | barge-in → silence | completion | answer P95 | duplicate lines | spoken, not displayed |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for sid, hs in hv["scenarios"].items():
            bs = bv["scenarios"].get(sid)
            if bs is None:
                lines.append(f"| {sid} | new in head: {_acc(hs['aggregate'].get('accuracy'))} | | | | | | | | |")
                continue
            ba, ha = bs["aggregate"], hs["aggregate"]

            def cell(key: str, q: str = "p50", ba: dict[str, Any] = ba, ha: dict[str, Any] = ha) -> str:
                return f"{_p(ba.get(key), q)} → {_p(ha.get(key), q)}{_delta(ba.get(key), ha.get(key), q)}"

            def total(key: str, ba: dict[str, Any] = ba, ha: dict[str, Any] = ha) -> str:
                b, h = (ba.get(key) or {}).get("total"), (ha.get(key) or {}).get("total")
                return f"{b if b is not None else '–'} → {h if h is not None else '–'}"

            lines.append(
                f"| {sid} | {_acc(ba.get('accuracy'))} → {_acc(ha.get('accuracy'))} | {cell('first_answer_played_ms')} | "
                f"{cell('first_any_played_ms')} | {cell('barge_to_quiet_ms')} | {cell('interrupt_to_silence_ms')} | "
                f"{cell('completion_ms')} | {cell('first_answer_played_ms', 'p95')} | {total('duplicate_lines')} | "
                f"{total('spoken_not_displayed_words')} |"
            )
        lines.append("")
    bc, hc = base.get("chat"), head.get("chat")
    if bc and hc:
        lines += [
            "## Chat turns (real wall clock: host-dependent, compare within this run only)",
            "",
            "| Surface : turn | P50 ms base → head | P95 ms base → head | web searches base → head | accuracy base → head |",
            "|---|---|---|---|---|",
        ]
        for key, h in hc["turns"].items():
            b = bc["turns"].get(key)
            if b is None:
                continue
            ba, ha = b["aggregate"], h["aggregate"]
            lines.append(
                f"| {key} | {ba['p50_ms']} → {ha['p50_ms']} | {ba['p95_ms']} → {ha['p95_ms']} | "
                f"{ba['mean_web_searches']} → {ha['mean_web_searches']} | {_acc(ba['accuracy'])} → {_acc(ha['accuracy'])} |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True, help="base revision (any git rev, or WORKTREE)")
    parser.add_argument("--head", default=CURRENT, help="head revision (default WORKTREE: the current checkout)")
    parser.add_argument("--profile", default="production_inferred", help="flag profile for both sides ('' for none)")
    parser.add_argument("--runs", type=int, default=20, help="voice runs per scenario")
    parser.add_argument("--seed", type=int, default=1000, help="voice seed base")
    parser.add_argument("--scenarios", default="", help="comma-separated voice scenario ids (default: all)")
    parser.add_argument("--chat-runs", type=int, default=0, help="chat-turn samples per turn (0: skip the chat bench)")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--revision-harness", action="store_true", help="use each revision's own bench driver")
    parser.add_argument("--keep-worktrees", action="store_true", help="leave the temporary worktrees in place")
    args = parser.parse_args(argv)

    out = Path(args.out).resolve()
    tmp = Path(tempfile.mkdtemp(prefix="bench-compare-"))
    created: list[Path] = []
    sides: dict[str, dict[str, Any]] = {}
    try:
        for side, rev in (("base", args.base), ("head", args.head)):
            backend, temporary = _checkout(rev, tmp, side)
            if temporary:
                created.append(backend.parent)
            if not args.revision_harness:
                _overlay_harness(backend)
            commit = _git("rev-parse", "--short", "HEAD", cwd=backend)
            app_tree = _git("rev-parse", "HEAD:backend/app", cwd=backend)
            if rev == CURRENT and _git("status", "--porcelain", "--", "app", cwd=backend):
                app_tree = f"{app_tree} + uncommitted edits"
            sides[side] = {
                "rev": rev,
                "commit": commit,
                "app_tree": app_tree,
                "backend": backend,
                "harness": "revision's own" if args.revision_harness else "current checkout's",
            }
        started = time.time()
        for side, info in sides.items():
            voice_out = out / side / "voice"
            cmd = [
                sys.executable, "scripts/bench_voice_scenarios.py", "--runs", str(args.runs), "--seed", str(args.seed),
                "--out", str(voice_out), "--label", f"{side} {info['rev']}",
            ]
            if args.profile:
                cmd += ["--profile", args.profile]
            if args.scenarios:
                cmd += ["--scenarios", args.scenarios]
            _run(cmd, info["backend"], out / side / "voice.log")
            info["voice"] = _load(voice_out / "results.json")
        if args.chat_runs:
            for side, info in sides.items():
                chat_out = out / side / "chat"
                cmd = [sys.executable, "scripts/bench_chat_turns.py", "--runs", str(args.chat_runs), "--out", str(chat_out),
                       "--label", f"{side} {info['rev']}"]
                _run(cmd, info["backend"], out / side / "chat.log")
                info["chat"] = _load(chat_out / "results.json")
        report = comparison_markdown(sides, args)
        report += f"\nTotal wall time {time.time() - started:.0f} s. Per-side results: base/ and head/ next to this file.\n"
        (out / "comparison.md").write_text(report)
        print(f"wrote {out / 'comparison.md'}")
    finally:
        if not args.keep_worktrees:
            for path in created:
                subprocess.call(["git", "worktree", "remove", "--force", str(path)], cwd=BACKEND_ROOT)
            shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
