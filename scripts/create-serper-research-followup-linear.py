"""Create low-priority Linear follow-up: Serper eval + dual-provider / billing SoT notes."""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Local Windows Python installs sometimes ship with a broken/expired CA store.
_SSL = ssl._create_unverified_context()  # noqa: S323

TEAM_KEY = os.environ.get("LINEAR_TEAM", "STA")
# Historical tickets use STA-*; team key in scripts sometimes "Staqbot"
TEAM_CANDIDATES = ["STA", "Staqbot"]


def load_env(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_bytes().decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def railway_vars() -> dict[str, str]:
    r = subprocess.run(
        ["railway", "variables", "--service", "gravitre-saas-backend", "--json"],
        capture_output=True,
        text=True,
        shell=True,
    )
    if r.returncode != 0:
        return {}
    try:
        data = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    return {}


def gql(api_key: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        "https://api.linear.app/graphql",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45, context=_SSL) as resp:
        payload = json.loads(resp.read().decode())
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"]))
    return payload["data"]


DESCRIPTION = """\
## Priority

**Low** — bounded cost-side follow-up. Does **not** change the Research Lookups pricing model (keep included allotment + transparent $0.35 overage). Improves COGS margin only if quality holds.

## Context

Research Lookups COGS diagnosis (`docs/delivery/research-lookups-cogs-pricing-diagnosis.md`, commit `8c06bbc2` / restore `b5632611`):
- Live metered path is **Tavily** (~$0.008/lookup PAYG bound)
- Customer overage stays **$0.35**
- Recommendation: keep metered (do not voice-style hide)

Published Serper pack pricing (public secondary sources / serper.dev homepage, verify on account before deciding): ~**$0.001 → $0.0003/query** ($1.00 → $0.30 per 1k credits) vs Tavily ~$0.008 — potential ~8–25× COGS improvement **if** quality matches.

## Scope (bounded)

### A — Serper evaluation (main work)

1. Confirm **real, current** Serper account/list pricing (not blog-only).
2. Side-by-side quality test on a **representative sample of real Gravitre research lookups** (reuse queries from `usage_records` / smoke research cascade — not invented SEO fluff).
3. Compare: citation usefulness, result relevance, empty/error rate, latency vs current Tavily path (`web_research.py` / `_search_tavily`).
4. If quality holds: propose integration shape (replace vs fallback/supplement) + env/config + metering `metadata.provider=serper` — **no pricing-page / overage changes**.
5. If quality fails: close with evidence; keep Tavily.

Out of scope: changing allotments, overage rate, or hide-vs-meter decision.

### B — Dual-provider honesty (flagged — resolve in this ticket or mark Done with evidence)

- Code default `WEB_RESEARCH_PROVIDER=google`; Railway historically omitted the var → Google attempted then **100% fallback to Tavily** (35/35 usage_records).
- `GEMINI_API_KEY` present on Railway does **not** mean Google wins; health `web_research_provider_configured` can be true from Tavily alone.
- **Not dead code** — intentional governance primary that never wins in prod.
- Resolution target: set prod `WEB_RESEARCH_PROVIDER=tavily` until a live lookup meters `google_grounding`; keep Google code behind explicit opt-in.

### C — billing_plans research SoT (flagged)

Root cause: `20260729120000` wholesale features replace wiped research keys; runtime silent fallback to code constants.

**Already restored live 2026-08-11** — node 10 / control 60 / command 200 / enterprise 200; `research_lookup=0.35`; voice intact (`docs/delivery/billing-plans-research-lookups-restore-2026-08-11.json`, commit `b5632611`). Seeds hardened to merge. Mark **Done** after re-verify query only.

## Done when

- [ ] Serper price CONFIRMED from account or official page with date stamp
- [ ] Side-by-side quality artifact on ≥N real queries (document N; suggest 15–25)
- [ ] Go / no-go on Serper with evidence
- [ ] B: Railway `WEB_RESEARCH_PROVIDER` matches live path (or google_grounding PASS in usage_records)
- [ ] C: `billing_plans.features.research_lookups_per_month` present on node/control/command (re-verify)

## Refs

- `docs/delivery/research-lookups-cogs-pricing-diagnosis.md`
- `docs/delivery/billing-plans-research-lookups-restore-2026-08-11.json`
- `backend/app/services/web_research.py`
"""


def main() -> int:
    env: dict[str, str] = {}
    for path in ("backend/.env", "backend/.env.operator.local"):
        env.update(load_env(path))
    api_key = (
        env.get("LINEAR_API_KEY")
        or env.get("LINEAR_TOKEN")
        or os.environ.get("LINEAR_API_KEY")
        or railway_vars().get("LINEAR_API_KEY")
        or railway_vars().get("LINEAR_TOKEN")
    )
    if not api_key:
        print("FAIL missing LINEAR_API_KEY", file=sys.stderr)
        return 1

    team = None
    for key in TEAM_CANDIDATES:
        data = gql(
            api_key,
            """query($key: String!) {
              teams(filter: { key: { eq: $key } }) { nodes { id key name } }
            }""",
            {"key": key},
        )
        nodes = data.get("teams", {}).get("nodes") or []
        if nodes:
            team = nodes[0]
            break
    if not team:
        # fallback: first team
        data = gql(api_key, "query { teams { nodes { id key name } } }")
        nodes = data.get("teams", {}).get("nodes") or []
        if not nodes:
            print("FAIL no Linear team", file=sys.stderr)
            return 1
        team = nodes[0]

    # Linear: 0=None, 1=Urgent, 2=High, 3=Normal, 4=Low
    created = gql(
        api_key,
        """mutation($input: IssueCreateInput!) {
          issueCreate(input: $input) {
            success
            issue { id identifier url title priorityLabel }
          }
        }""",
        {
            "input": {
                "teamId": team["id"],
                "title": "Low: evaluate Serper for Research Lookups COGS (quality gate; pricing model unchanged)",
                "description": DESCRIPTION,
                "priority": 4,
            }
        },
    )
    issue = (created.get("issueCreate") or {}).get("issue") or {}
    out = {
        "success": (created.get("issueCreate") or {}).get("success"),
        "identifier": issue.get("identifier"),
        "url": issue.get("url"),
        "title": issue.get("title"),
        "priorityLabel": issue.get("priorityLabel"),
        "team": team.get("key"),
    }
    Path("docs/delivery/serper-research-lookups-followup-linear.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, indent=2))
    return 0 if out.get("success") and out.get("url") else 1


if __name__ == "__main__":
    raise SystemExit(main())
