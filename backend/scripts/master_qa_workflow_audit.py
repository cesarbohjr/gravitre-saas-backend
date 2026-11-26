"""Read-only static workflow risk/dependency audit, no token or live API use.

Outputs facts from workflow YAML source, never secrets or guessed operating costs.
GitHub branch-protection policy and historical Actions billing require separate
privileged readbacks; absence of evidence is NOT permission to consolidate.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

JOB_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$", re.M)
EVENT_RE = re.compile(r"^  (push|pull_request|pull_request_target|workflow_dispatch|workflow_call|schedule|repository_dispatch|workflow_run):\s*", re.M)
SECRET_RE = re.compile(r"secrets\.([A-Za-z_][A-Za-z_0-9]*)")
VARS_RE = re.compile(r"vars\.([A-Za-z_][A-Za-z_0-9]*)")
USES_RE = re.compile(r"^\s+uses:\s*(\S+)", re.M)
ENVS_RE = re.compile(r"^\s+environment:\s*(\S+)", re.M)
JOB_WITH_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$", re.M)
NETWORK_HINTS = ("curl ", "wget ", "requests.", "httpx.", "vercel deploy", "railway ", "supabase ", "stripe ")
DEPLOY_HINTS = ("deploy", "railway", "vercel", "production", "migrate", "cutover")
ROOT = Path(__file__).resolve().parents[2]


def inventory(root: Path = ROOT) -> dict:
    directory = root / ".github" / "workflows"
    records = []
    if not directory.is_dir():
        raise ValueError("workflow directory not found")
    for path in sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")]):
        raw = path.read_text()
        # YAML may include secrets in opaque values: only emit REF NAMES, never values.
        head = raw.split("\njobs:", 1)[0]
        triggers = sorted(set(EVENT_RE.findall(head)))
        calls = sorted({u for u in USES_RE.findall(raw) if u.startswith("./.github/workflows/")})
        envs = sorted(set(ENVS_RE.findall(raw)))
        secret_names = sorted(set(SECRET_RE.findall(raw)))
        uses = sorted(set(USES_RE.findall(raw)))
        refs = sorted(set(VARS_RE.findall(raw)))
        lines = raw.lower()
        production_risk = bool(any(k in lines for k in DEPLOY_HINTS)) or "production" in envs
        network_risk = bool(secret_names or any(k in lines for k in NETWORK_HINTS))
        records.append({
            "path": path.relative_to(root).as_posix(),
            "name": re.search(r"^name:\s*(.+)$", raw, re.M).group(1).strip() if re.search(r"^name:\s*(.+)$", raw, re.M) else None,
            "event_stanzas": triggers,
            "referenced_secret_names_only": secret_names,
            "referenced_variable_names_only": refs,
            "job_environment_tokens": envs,
            "workflow_call_dependencies": calls,
            "action_uses": uses,
            "static_production_side_effect_risk": "REVIEW_REQUIRED" if production_risk else "NOT_ESTABLISHED",
            "static_network_or_provider_risk": "REVIEW_REQUIRED" if network_risk else "NOT_ESTABLISHED",
            "required_check_state": "UNKNOWN_NEEDS_AUTHORIZED_GITHUB_READBACK",
            "runtime_minutes": None,
            "actual_spend": None,
            "active_status": "UNKNOWN_NEEDS_GITHUB_READBACK",
            "disposition": "INVESTIGATE",
            "retirement_authorized": False,
        })
    parents = {}
    for r in records:
        for dep in r["workflow_call_dependencies"]:
            parents.setdefault(dep.removeprefix("./"), []).append(r["path"])
    for r in records:
        r["known_local_callers"] = sorted(parents.get(r["path"], []))
    return {
        "schema_version": 1,
        "source_only": True,
        "note": "Static evidence; no required check/active workflow/cost/deploy permission claim.",
        "source_workflow_count": len(records),
        "requires_external_readback": [
            "actual enabled/disabled state", "main branch required checks",
            "recent run IDs, total runtime and artifacts", "billing minutes/storage",
            "external callers/dispatchers", "secrets scope and effective permissions",
        ],
        "workflows": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    record = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Audited {record['source_workflow_count']} workflow source files; no live effects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
