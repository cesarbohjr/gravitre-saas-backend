#!/usr/bin/env python3
"""Full-catalog retrieval enrichment generator (examples + functional tags).

LLM-assisted batch generation for every ActionSpec, with schema/behavior
validation and deterministic repair for any rejected rows. Writes:

  backend/app/connectors/action_catalog/data/action_retrieval_enrichment_full.json
  docs/delivery/action-retrieval-enrichment-generation-report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

OUT_JSON = (
    BACKEND
    / "app"
    / "connectors"
    / "action_catalog"
    / "data"
    / "action_retrieval_enrichment_full.json"
)
REPORT = ROOT / "docs" / "delivery" / "action-retrieval-enrichment-generation-report.json"

# Shared taxonomy — every action gets kind + vendor + resource + domain tags.
DOMAIN_BY_VENDOR: dict[str, str] = {
    "hubspot": "crm",
    "salesforce": "crm",
    "apollo": "sales",
    "pipedrive": "crm",
    "close": "crm",
    "gmail": "email",
    "outlook": "email",
    "slack": "chat",
    "teams": "chat",
    "intercom": "support",
    "zendesk": "support",
    "freshdesk": "support",
    "github": "devops",
    "gitlab": "devops",
    "jira": "project",
    "linear": "project",
    "asana": "project",
    "clickup": "project",
    "monday": "project",
    "notion": "docs",
    "confluence": "docs",
    "airtable": "data",
    "google_sheets": "data",
    "stripe": "finance",
    "quickbooks": "finance",
    "xero": "finance",
    "shopify": "commerce",
    "clay": "enrichment",
}

KIND_TAGS = {
    "read": ["read", "lookup"],
    "write": ["write", "mutate"],
    "advanced": ["advanced", "workflow"],
}

VERB_HINTS = {
    "search": ["find", "look up", "search for"],
    "list": ["list", "show me", "get all"],
    "get": ["get", "fetch", "pull details for"],
    "create": ["create", "make a new", "add"],
    "update": ["update", "change", "edit"],
    "delete": ["delete", "remove", "archive"],
    "send": ["send", "email", "message"],
    "post": ["post", "publish", "send"],
}


def _load_dotenv() -> None:
    try:
        from dotenv import dotenv_values
    except ImportError:
        return
    for p in (BACKEND / ".env.operator.local", BACKEND / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(p, encoding=enc).items():
                    if v and k not in os.environ:
                        os.environ[k] = v
                break
            except UnicodeDecodeError:
                continue


def _parts(action_id: str) -> tuple[str, str, str]:
    bits = action_id.split(".")
    vendor = bits[0] if bits else "unknown"
    resource = bits[1] if len(bits) > 1 else "record"
    verb = bits[-1] if len(bits) > 2 else (bits[1] if len(bits) > 1 else "run")
    return vendor, resource, verb


def _display_vendor(vendor: str) -> str:
    special = {
        "google_sheets": "Google Sheets",
        "google_drive": "Google Drive",
        "google_calendar": "Google Calendar",
        "microsoft_teams": "Microsoft Teams",
    }
    if vendor in special:
        return special[vendor]
    return vendor.replace("_", " ").title()


def deterministic_tags(spec: Any) -> list[str]:
    vendor, resource, verb = _parts(spec.id)
    tags: list[str] = []
    tags.extend(KIND_TAGS.get(str(spec.kind), ["action"]))
    tags.append(vendor)
    tags.append(resource.replace("_", "-"))
    tags.append(verb.replace("_", "-"))
    domain = DOMAIN_BY_VENDOR.get(vendor)
    if domain:
        tags.append(domain)
    if verb in ("search", "list", "find", "query"):
        tags.append("lookup")
    if verb in ("create", "add", "insert"):
        tags.append("create")
    if verb in ("send", "post", "notify"):
        tags.append("notify")
    # de-dupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        t = str(t).strip().lower()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:10]


def deterministic_examples(spec: Any) -> list[str]:
    vendor, resource, verb = _parts(spec.id)
    disp = _display_vendor(vendor)
    res = resource.replace("_", " ")
    name = (spec.name or "").strip() or f"{verb} {res}"
    hints = VERB_HINTS.get(verb, [verb.replace("_", " "), f"please {verb.replace('_', ' ')}"])
    examples = [
        f"{hints[0]} {disp} {res}",
        f"{hints[1] if len(hints) > 1 else hints[0]} my {disp} {res}",
        f"Can you {verb.replace('_', ' ')} {res} in {disp}?",
        f"{name} in {disp}",
        f"I need to {verb.replace('_', ' ')} a {res} on {disp}",
    ]
    # kind-aware casual variants
    if spec.kind == "write":
        examples.append(f"go ahead and {verb.replace('_', ' ')} that {res} in {disp}")
    else:
        examples.append(f"show me {disp} {res} matching Acme")
    # uniqueness
    seen: set[str] = set()
    out: list[str] = []
    for e in examples:
        e = " ".join(e.split())
        key = e.lower()
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out[:5]


def validate_row(spec: Any, row: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    examples = row.get("examples") or []
    tags = row.get("tags") or []
    if not isinstance(examples, list) or len(examples) < 3:
        errors.append("need>=3_examples")
    if not isinstance(tags, list) or len(tags) < 3:
        errors.append("need>=3_tags")
    vendor, resource, verb = _parts(spec.id)
    vendor_tokens = {vendor, vendor.replace("_", " "), _display_vendor(vendor).lower()}
    resource_tokens = {resource, resource.replace("_", " "), resource.replace("_", "-")}
    verb_tokens = {verb, verb.replace("_", " ")}
    # At least 2 examples must mention vendor OR resource (action-specific grounding)
    grounded = 0
    for ex in examples[:5]:
        low = str(ex).lower()
        if any(t.lower() in low for t in vendor_tokens if len(t) >= 3):
            grounded += 1
            continue
        if any(t.lower() in low for t in resource_tokens if len(t) >= 3):
            grounded += 1
    if grounded < 2:
        errors.append("examples_not_grounded")
    # Reject examples that clearly point at a different major vendor
    other_vendors = {
        "hubspot",
        "salesforce",
        "apollo",
        "gmail",
        "slack",
        "github",
        "clickup",
        "monday",
        "asana",
        "notion",
        "zendesk",
        "intercom",
        "linear",
        "jira",
        "airtable",
    } - {vendor}
    for ex in examples[:5]:
        low = str(ex).lower()
        for ov in other_vendors:
            if ov in low and ov not in vendor and ov.replace("_", " ") not in vendor:
                # allow if also mentions correct vendor
                if not any(t.lower() in low for t in vendor_tokens if len(str(t)) >= 3):
                    errors.append(f"cross_vendor:{ov}")
                    break
    tag_blob = " ".join(str(t).lower() for t in tags)
    if vendor not in tag_blob and vendor.replace("_", "-") not in tag_blob:
        errors.append("tags_missing_vendor")
    if str(spec.kind) not in ("read", "write", "advanced"):
        errors.append("bad_kind")
    elif str(spec.kind) not in tag_blob and not any(
        k in tag_blob for k in KIND_TAGS.get(str(spec.kind), [])
    ):
        errors.append("tags_missing_kind")
    return (len(errors) == 0), errors


def repair_row(spec: Any, row: dict[str, Any] | None) -> dict[str, Any]:
    base_ex = list((row or {}).get("examples") or [])
    base_tags = list((row or {}).get("tags") or [])
    det_ex = deterministic_examples(spec)
    det_tags = deterministic_tags(spec)
    examples: list[str] = []
    seen: set[str] = set()
    for e in base_ex + det_ex:
        e = " ".join(str(e).split())
        if len(e) < 8:
            continue
        k = e.lower()
        if k in seen:
            continue
        seen.add(k)
        examples.append(e)
        if len(examples) >= 5:
            break
    tags: list[str] = []
    tseen: set[str] = set()
    for t in base_tags + det_tags:
        t = str(t).strip().lower().replace(" ", "-")
        if not t or t in tseen:
            continue
        tseen.add(t)
        tags.append(t)
        if len(tags) >= 10:
            break
    return {"examples": examples[:5], "tags": tags[:10]}


def _openai_client():
    from openai import OpenAI

    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY missing")
    return OpenAI(api_key=key)


def llm_batch(specs: list[Any], *, model: str) -> dict[str, dict[str, Any]]:
    client = _openai_client()
    payload = []
    for s in specs:
        vendor, resource, verb = _parts(s.id)
        payload.append(
            {
                "id": s.id,
                "name": s.name,
                "kind": s.kind,
                "description": (s.description or "")[:280],
                "vendor": vendor,
                "resource": resource,
                "verb": verb,
            }
        )
    system = (
        "You generate retrieval enrichment for API tool actions. "
        "For each action return JSON object keyed by action id with: "
        '{"examples":[3-5 natural user phrasings], "tags":[5-8 short keywords]}. '
        "Examples must be distinct natural-language requests a real user would type "
        "(casual + formal, varied verbs). Each example MUST mention the correct vendor "
        "or an unambiguous product name, and must match what the action does. "
        "Tags use lowercase hyphenated tokens; always include vendor, resource, "
        "kind (read|write|advanced), and domain. "
        "Return ONLY a JSON object, no markdown."
    )
    user = json.dumps({"actions": payload}, ensure_ascii=False)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content or "{}"
    data = json.loads(text)
    # Allow wrapped {"actions": {...}} or flat map
    if isinstance(data.get("actions"), dict):
        data = data["actions"]
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(data, dict):
        return out
    for k, v in data.items():
        if isinstance(v, dict):
            out[str(k).strip().lower()] = v
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--model", default=os.environ.get("ENRICH_GEN_MODEL", "gpt-4o-mini"))
    parser.add_argument("--deterministic-only", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Debug: only first N actions")
    args = parser.parse_args()
    _load_dotenv()

    from app.connectors.action_catalog.registry import all_catalog_action_specs, get_vendor_catalog

    specs = list(all_catalog_action_specs())
    if args.limit > 0:
        specs = specs[: args.limit]
    vendors = len(get_vendor_catalog())

    actions: dict[str, dict[str, Any]] = {}
    stats = Counter()
    failures: list[dict[str, Any]] = []

    # Seed with prior hand-authored sample when present
    from app.connectors.action_catalog.action_retrieval_enrichment import (
        ACTION_RETRIEVAL_ENRICHMENT as PILOT,
    )

    for aid, row in PILOT.items():
        actions[aid] = {
            "examples": list(row.get("examples") or []),
            "tags": list(row.get("tags") or []),
            "source": "pilot",
        }

    t0 = time.perf_counter()
    if args.deterministic_only:
        for s in specs:
            actions[s.id] = {**repair_row(s, actions.get(s.id)), "source": "deterministic"}
            stats["deterministic"] += 1
    else:
        pending = [s for s in specs if s.id not in actions or len(actions[s.id].get("examples") or []) < 3]
        # Also regenerate pilot rows through validation/repair later; keep pilot content as seed.
        pending = list(specs)
        for i in range(0, len(pending), args.batch_size):
            batch = pending[i : i + args.batch_size]
            try:
                llm_rows = llm_batch(batch, model=args.model)
                stats["llm_batches"] += 1
            except Exception as exc:  # noqa: BLE001
                stats["llm_batch_errors"] += 1
                llm_rows = {}
                failures.append({"batch_start": batch[0].id, "error": str(exc)[:240]})
            for s in batch:
                raw = llm_rows.get(s.id.lower()) or llm_rows.get(s.id) or actions.get(s.id)
                repaired = repair_row(s, raw if isinstance(raw, dict) else None)
                ok, errs = validate_row(s, repaired)
                if not ok:
                    repaired = repair_row(s, None)
                    ok2, errs2 = validate_row(s, repaired)
                    stats["repaired"] += 1
                    if not ok2:
                        failures.append({"id": s.id, "errors": errs2})
                        stats["invalid_after_repair"] += 1
                    source = "deterministic_repair"
                else:
                    source = "llm+validate" if raw else "deterministic"
                    stats["llm_ok" if raw else "deterministic"] += 1
                actions[s.id] = {**repaired, "source": source}
            print(
                f"batch {i // args.batch_size + 1}/"
                f"{(len(pending) + args.batch_size - 1) // args.batch_size} "
                f"covered={len(actions)}",
                flush=True,
            )
            time.sleep(0.15)

    # Final pass: guarantee every catalog action present + valid (catalog ids only)
    final_actions: dict[str, dict[str, Any]] = {}
    for s in specs:
        row = repair_row(s, actions.get(s.id))
        ok, errs = validate_row(s, row)
        if not ok:
            row = repair_row(s, None)
            ok, errs = validate_row(s, row)
        final_actions[s.id] = {
            "examples": row["examples"],
            "tags": row["tags"],
            "source": (actions.get(s.id) or {}).get("source") or "final",
        }
        if not ok:
            failures.append({"id": s.id, "errors": errs, "phase": "final"})
    actions = final_actions

    missing = [s.id for s in specs if s.id not in actions]
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    doc = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalog_action_count": len(specs),
        "vendor_count": vendors,
        "enriched_action_count": len(actions),
        "generator_model": None if args.deterministic_only else args.model,
        "taxonomy_version": 1,
        "actions": {
            k: {"examples": v["examples"], "tags": v["tags"]}
            for k, v in sorted(actions.items())
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "generated_at": doc["generated_at"],
        "catalog_action_count": len(specs),
        "vendor_count": vendors,
        "enriched_action_count": len(actions),
        "coverage_pct": round(100.0 * len(actions) / max(1, len(specs)), 2),
        "missing": missing,
        "stats": dict(stats),
        "failure_count": len(failures),
        "failures_sample": failures[:20],
        "elapsed_ms": elapsed_ms,
        "out": str(OUT_JSON),
        "full_coverage": len(missing) == 0 and len(actions) >= len(specs),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["full_coverage"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
