#!/usr/bin/env python3
"""Live proof for instance 2: the non-OpenAI unified-turn tool attach.

The 8 `unnarrowed_tool_attach_blocked at provider_tool_router.complete_with_tools`
events of 2026-08-12/13 came from the unified turn's non-OpenAI branch. Prod
routes unified turns to OpenAI models, which take the streaming branch and never
call `complete_with_tools`, so the defect stopped producing events without being
fixed. This probe deliberately routes a real, tool-carrying unified turn to
Anthropic so the path is exercised for real.

Safety, deliberately bounded:

  * `run_unified_turn_shadow` makes ONE model call and does not execute tools
    (see its docstring). No connector write can occur, by construction.
  * Runs in the isolated conversation org, which is guarded against ever being a
    customer org (`conversation_write_guard`), never Cesar's workspace.
  * Does not change prod routing, prod config, or any agent a customer can
    reach. The Anthropic model is passed per-call, in-process.
  * Asserts the OpenAI tool path is NOT taken, so a pass cannot be manufactured
    by silently falling back to OpenAI.
  * Read-shaped prompt (connector status), no destructive vocabulary.

Run pre-fix and post-fix to get a real before/after:

    python scripts/probe-unnarrowed-nonopenai-live.py --label pre-fix
    python scripts/probe-unnarrowed-nonopenai-live.py --label post-fix
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO / "scripts"))

from dotenv import dotenv_values  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

PROD_HEALTH = "https://api.gravitre.app/health"
OUT = REPO / "docs" / "delivery" / "unnarrowed-nonopenai-live.json"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
GUARD_TOKEN = "unnarrowed_tool_attach_blocked"
ATTACH_SITE = "provider_tool_router.complete_with_tools"

# Task-shaped and tool-carrying: must clear is_task_shaped_for_retrieval so the
# turn actually attaches tools. A conversational message would attach none and
# the probe would prove nothing.
MESSAGE = "search my apollo lists and tell me which integrations are connected"


class OpenAIToolPathTaken(RuntimeError):
    """The probe fell back to OpenAI; an Anthropic result would be a false pass."""


def _load_env() -> list[str]:
    """Load env files, trying real encodings. Returns per-file status.

    These files are cp1252 on this machine, not utf-8. An earlier version used
    the dotenv default and swallowed UnicodeDecodeError per file, which skipped
    every variable in it and surfaced as `anthropic_not_configured` -- a missing
    key, not a parse failure. Same class as the bug under investigation: a
    silent skip read as a clean negative. So the status is returned and
    recorded, never swallowed.
    """
    status: list[str] = []
    for path in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if not path.is_file():
            status.append(f"{path.name}: absent")
            continue
        loaded = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                loaded = dotenv_values(path, encoding=enc)
                break
            except UnicodeDecodeError:
                continue
        if loaded is None:
            status.append(f"{path.name}: UNREADABLE in all encodings")
            continue
        applied = 0
        for key, value in loaded.items():
            if value and key not in os.environ:
                os.environ[key] = value
                applied += 1
        status.append(f"{path.name}: {applied} vars applied of {len(loaded)} ({enc})")
    return status


def _health() -> dict[str, Any]:
    import urllib.request

    with urllib.request.urlopen(PROD_HEALTH, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


@asynccontextmanager
async def _forbid_openai_tools(router: Any):
    """Fail loudly if the turn attaches tools via OpenAI instead of Anthropic."""
    client = getattr(router, "_openai", None)
    if client is None:
        yield
        return
    original = client.chat.completions.create

    async def _guarded(**kwargs: Any) -> Any:
        if kwargs.get("tools"):
            raise OpenAIToolPathTaken(
                "OpenAI tool path invoked during an Anthropic probe"
            )
        return await original(**kwargs)

    client.chat.completions.create = _guarded
    try:
        yield
    finally:
        client.chat.completions.create = original


async def _run(label: str) -> dict[str, Any]:
    env_status = _load_env()

    from app.config import get_settings
    from app.services.model_router import get_model_router
    from app.services.providers.provider_tool_router import (
        provider_tools_configured,
        resolve_provider_for_model,
    )
    from app.services.unified_turn_reasoning_service import run_unified_turn_shadow
    from app.workflows.repository import get_supabase_client
    from isolated_conversation_org import (
        FORBIDDEN_OPERATOR_ORG_ID,
        mark_smoke_run,
        resolve_isolated_conversation_actor,
    )

    mark_smoke_run()
    settings = get_settings()
    client = get_supabase_client(settings)
    org_id, actor_id, _email = resolve_isolated_conversation_actor(dict(os.environ), client)

    if str(org_id) == str(FORBIDDEN_OPERATOR_ORG_ID):
        raise SystemExit("refusing to probe against the operator org")

    report: dict[str, Any] = {
        "probe": "unnarrowed_tool_attach_nonopenai",
        "label": label,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "env_files": env_status,
        "org_id": org_id,
        "org_is_isolated": True,
        "model": ANTHROPIC_MODEL,
        "provider": resolve_provider_for_model(ANTHROPIC_MODEL),
        # Booleans only; no secret material is read or recorded.
        "provider_configured": {
            p: bool(provider_tools_configured(p, settings))
            for p in ("openai", "anthropic")
        },
        "deployed_health": _health(),
        "local_git_sha": os.popen("git rev-parse HEAD").read().strip()[:12],
    }

    if not report["provider_configured"]["anthropic"]:
        report["verdict"] = "CANNOT_RUN"
        report["reason"] = "anthropic_not_configured in this environment"
        return report

    # Shadow must be on for the turn to run at all; note it if we force it.
    forced = []
    for flag in ("unified_turn_shadow_enabled",):
        if not getattr(settings, flag, False):
            try:
                object.__setattr__(settings, flag, True)
                forced.append(flag)
            except Exception:
                setattr(settings, flag, True)
                forced.append(flag)
    report["forced_flags"] = forced

    router = get_model_router()
    openai_tool_path_taken = False
    try:
        async with _forbid_openai_tools(router):
            result = await run_unified_turn_shadow(
                org_id=org_id,
                user_id=actor_id,
                conversation_id=None,
                message=MESSAGE,
                task_state=None,
                conversation_history=None,
                connected_integrations=["platform", "apollo"],
                client=client,
                settings=settings,
                agent={"model": ANTHROPIC_MODEL, "name": "unnarrowed nonopenai probe"},
                permitted_tools=["*"],
            )
    except OpenAIToolPathTaken as exc:
        openai_tool_path_taken = True
        report["verdict"] = "INVALID"
        report["reason"] = str(exc)
        return report

    error = str(getattr(result, "error", "") or "")
    outcome = str(getattr(result, "outcome_kind", "") or "")
    report.update(
        {
            "openai_tool_path_taken": openai_tool_path_taken,
            "outcome_kind": outcome,
            "error": error[:500],
            "model_used": getattr(result, "model", None),
            "tool_name": getattr(result, "tool_name", None),
            "user_message_snippet": str(getattr(result, "user_message", "") or "")[:220],
            "tool_stats_method": (getattr(result, "tool_stats", None) or {}).get(
                "retrievalMethod"
            ),
            # "visibleTools", not "visibleToolCount" -- the first attempt read a
            # key that does not exist and recorded None, which would have made a
            # CLEAN verdict unfalsifiable (a turn attaching zero tools can never
            # trip the guard). Both spellings are recorded so a future rename
            # shows up as a mismatch rather than a silent None.
            "attached_tool_count": (getattr(result, "tool_stats", None) or {}).get(
                "visibleTools"
            ),
            "attached_tool_count_legacy_key": (
                getattr(result, "tool_stats", None) or {}
            ).get("visibleToolCount"),
            "tool_stats": getattr(result, "tool_stats", None) or {},
        }
    )

    guard_fired = GUARD_TOKEN in error
    at_this_site = ATTACH_SITE in error
    report["guard_fired"] = guard_fired
    report["guard_at_expected_site"] = at_this_site

    if guard_fired and at_this_site:
        report["verdict"] = "BUG_REPRODUCED"
    elif guard_fired:
        report["verdict"] = "GUARD_FIRED_ELSEWHERE"
    elif outcome == "error":
        report["verdict"] = "OTHER_ERROR"
    else:
        # A clean pass only counts if the turn genuinely carried tools: a turn
        # that attached none could never trip the guard, so CLEAN would be
        # unfalsifiable. Enforced, not merely asserted in a comment.
        carried = int(report.get("attached_tool_count") or 0)
        chose_tool = bool(report.get("tool_name"))
        if carried > 0 or chose_tool:
            report["verdict"] = "CLEAN"
        else:
            report["verdict"] = "VACUOUS_NO_TOOLS_ATTACHED"
        report["clean_is_falsifiable"] = carried > 0 or chose_tool

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="run")
    parser.add_argument("--json", dest="json_path", default=str(OUT))
    args = parser.parse_args()

    report = asyncio.run(_run(args.label))

    path = Path(args.json_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.is_file():
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
            existing = prior if isinstance(prior, list) else [prior]
        except json.JSONDecodeError:
            existing = []
    existing.append(report)
    path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")

    print(f"label            : {report.get('label')}")
    for line in report.get("env_files") or []:
        print(f"  env            : {line}")
    print(f"local sha        : {report.get('local_git_sha')}")
    print(f"prod sha         : {(report.get('deployed_health') or {}).get('git_sha', '')[:12]}")
    print(f"provider         : {report.get('provider')} / {report.get('model')}")
    print(f"anthropic key    : {(report.get('provider_configured') or {}).get('anthropic')}")
    print(f"outcome_kind     : {report.get('outcome_kind')}")
    print(f"guard fired      : {report.get('guard_fired')} at expected site={report.get('guard_at_expected_site')}")
    print(f"error            : {(report.get('error') or '')[:160]}")
    print(f"reply snippet    : {report.get('user_message_snippet')}")
    print(f"VERDICT          : {report.get('verdict')}")
    print(f"wrote            : {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
