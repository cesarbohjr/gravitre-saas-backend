"""Module D expression range — phrase variety for recurring voice categories.

Varies sentence construction only. Facts (integration, paths, field names, error
codes) stay identical across variants. Selection is deterministic rotation per
conversation via ``task_state.voice_expression_last`` (no model call).

Precision-critical kinds are excluded — see ``EXPRESSION_EXCLUDED``.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import re
from typing import Any, Mapping, Sequence

logger = logging.getLogger(__name__)

# Categories where variation would hurt clarity / auditability.
EXPRESSION_EXCLUDED: frozenset[str] = frozenset(
    {
        "write_approval",
        "write_approval_required",
        "canvas_write_blocked",
        "canvas_write_authority_blocked",
        "approval_needed_requester",
        "approval_needed_requester_title",
        "notification_run_title",
        "audit_failure_summary",
        "failure_alert_title",
    }
)

# 5–8 variants each. Placeholders use the same format keys as today.
EXPRESSION_BANKS: dict[str, tuple[str, ...]] = {
    "connector_connect_to_run": (
        "Connect {integration} at /connectors to run this action.",
        "This needs {integration}, and it is not Connected yet. Set it up at /connectors, then try again.",
        "I cannot reach {integration} — it is not Connected. Connect it at /connectors and I will pick this back up.",
        "{integration} is not Connected for this organization. Open /connectors, connect it, then retry.",
        "Blocked on {integration}: not Connected. Connect it at /connectors, then run this again.",
        "No Connected {integration} link yet. Finish setup at /connectors, then retry this action.",
    ),
    "skipped_connector": (
        "Skipped — {integration} is not Connected.",
        "Skipped this step because {integration} is not Connected.",
        "Could not run this step — {integration} is not Connected.",
        "Step skipped: {integration} has no Connected link for this organization.",
        "Passed over this step; {integration} is not Connected yet.",
    ),
    "insufficient_info": (
        "I don't have enough information yet. Tell me the missing detail and I'll continue.",
        "I am missing a detail I need before I can continue. Share it and I will proceed.",
        "Not enough to go on yet. Give me the missing piece and I will continue.",
        "I still need one more detail to proceed. Reply with it and I will keep going.",
        "This is blocked on missing information. Send the detail I need and I will continue.",
        "I cannot finish from what I have. Tell me what is missing and I will pick it up.",
    ),
    "assumption_flag": (
        "Assumption — based on what's Connected so far; say if that is wrong.",
        "I am treating this as an assumption from what is Connected so far — correct me if it is wrong.",
        "Working assumption from Connected state; tell me if that is off.",
        "Inferred from what is Connected so far — say if I should use something else.",
        "Assumption from current Connected context; push back if that is incorrect.",
    ),
    "success_win": (
        "Done. Verified output is ready.",
        "Finished. Verified output is ready.",
        "Complete — Verified output is ready.",
        "That run finished. Verified output is ready.",
        "All set. Verified output is ready.",
        "Done — Verified output is ready for you.",
    ),
    "success_win_light": (
        "Done — clean run.",
        "Finished — clean run.",
        "That one landed cleanly.",
        "Clean run — done.",
        "All clear — clean run.",
    ),
    "blocked_generic": (
        "Blocked. {blocker} Next: {next_action}",
        "Blocked on this: {blocker} Next: {next_action}",
        "Cannot proceed. {blocker} Next: {next_action}",
        "This is blocked. {blocker} Next step: {next_action}",
        "Stopped here. {blocker} Next: {next_action}",
        "Blocked — {blocker} Next: {next_action}",
    ),
    "skipped_unsupported": (
        "Skipped — no Executable action matched this step.",
        "Skipped this step — nothing Executable matched it.",
        "No Executable action matched this step, so it was skipped.",
        "Step skipped: no Executable match in the catalog.",
        "Passed over — no Executable action for this step.",
    ),
    "no_executable_action": (
        "No Executable action matched this request.",
        "I could not find an Executable action that matches this request.",
        "Nothing Executable lines up with that request.",
        "No catalog action is Executable for this ask.",
        "I do not have an Executable action that maps to this request.",
    ),
    "correction_ack": (
        "Got it — updated to {correction}. Continuing with that.",
        "Understood — switched to {correction}. Continuing from there.",
        "Noted — using {correction} now and continuing.",
        "Correction applied: {correction}. Picking up from there.",
        "Updated to {correction}. Continuing with that.",
        "Got the correction — {correction}. Moving forward with it.",
    ),
    "pending_plan_cancelled": (
        "Cancelled the pending plan. What should we do instead?",
        "Pending plan cleared. What next?",
        "I cancelled that pending plan. What should we do instead?",
        "That pending plan is gone. What would you like to do now?",
        "Cancelled — no pending plan left. What should we do instead?",
        "Cleared the pending plan. Tell me the next move.",
    ),
    "estimate_prefix": (
        "Estimate — based on what's Connected so far:",
        "Estimate from what's Connected so far:",
        "Estimate (Connected state only):",
        "Estimate — Connected signals only:",
        "Rough estimate from what's Connected so far:",
    ),
    "missing_parameters_header": (
        "Still needed:",
        "I still need:",
        "Missing before I can continue:",
        "To proceed I still need:",
        "Outstanding details:",
        "Not yet filled in:",
    ),
    # tool_error codes (same facts: integration, /connectors, action_suffix)
    "tool_error.auth_expired": (
        "{integration} authentication expired. Reconnect it at /connectors, then try again.",
        "{integration} auth expired. Reconnect at /connectors, then retry.",
        "Authentication for {integration} has expired. Reconnect it at /connectors and try again.",
        "{integration} needs a reconnect — authentication expired. Fix it at /connectors, then retry.",
        "Blocked: {integration} authentication expired. Reconnect at /connectors, then try again.",
        "{integration} is no longer Authenticated. Reconnect at /connectors, then retry.",
    ),
    "tool_error.permission_denied": (
        "You do not have permission to run this action{action_suffix}. Ask an admin to grant access, or pick a different tool.",
        "Permission denied for this action{action_suffix}. Ask an admin for access, or choose another tool.",
        "You are not allowed to run this action{action_suffix}. Get access from an admin, or pick a different tool.",
        "This action{action_suffix} is not permitted for your role. Ask an admin, or use a different tool.",
        "Blocked by permission on this action{action_suffix}. Request access from an admin, or switch tools.",
    ),
    "tool_error.connector_not_connected": (
        "{integration} is not Connected for this organization. Connect it now at /connectors, or reply **yes** to open the connect flow, then try again.",
        "{integration} is not Connected here. Connect it at /connectors (or reply **yes** for the connect flow), then retry.",
        "No Connected {integration} for this organization. Open /connectors or reply **yes** to connect, then try again.",
        "I cannot use {integration} — it is not Connected. Connect at /connectors or reply **yes**, then retry.",
        "{integration} has no Connected link yet. Set it up at /connectors (reply **yes** to open connect), then try again.",
        "Blocked: {integration} is not Connected. Connect at /connectors or say **yes** for the connect flow, then retry.",
    ),
    "tool_error.channel_not_found": (
        "That Slack channel was not found (or the bot is not a member). Use a public channel name/id the bot can access, invite the bot, then try again.",
        "Slack channel missing or the bot is not a member. Pick a public channel the bot can access, invite it, then retry.",
        "I could not find that Slack channel (or the bot is not in it). Use a reachable public channel, invite the bot, then try again.",
        "Channel not found for Slack — or the bot is not a member. Correct the channel, invite the bot, then retry.",
        "That Slack channel is unavailable to the bot. Use a public channel it can access, invite it, then try again.",
    ),
    "tool_error.missing_scope": (
        "{integration} is Connected but missing required permissions{action_suffix}. Reconnect it at /connectors and approve the requested scopes.",
        "{integration} is Connected without the scopes needed{action_suffix}. Reconnect at /connectors and approve the missing permissions.",
        "Connected {integration} is missing permissions{action_suffix}. Reconnect at /connectors and grant the requested scopes.",
        "{integration} needs additional scopes{action_suffix}. Reconnect at /connectors and approve them, then retry.",
        "Blocked: {integration} Connected but under-scoped{action_suffix}. Reconnect at /connectors and approve the required permissions.",
    ),
    "tool_error.validation_error": (
        "Invalid parameters for this {integration} action{action_suffix}. Check required fields and try again.",
        "Those parameters are not valid for this {integration} action{action_suffix}. Fix the required fields and retry.",
        "{integration} rejected the parameters{action_suffix}. Check required fields and try again.",
        "Parameter validation failed for {integration}{action_suffix}. Correct the required fields, then retry.",
        "Invalid input for this {integration} action{action_suffix}. Review required fields and try again.",
    ),
    "tool_error.rate_limited": (
        "{integration} rate-limited the request. Wait a moment and try again.",
        "{integration} hit a rate limit. Pause briefly, then retry.",
        "Rate limited by {integration}. Wait a moment and try again.",
        "{integration} asked us to slow down. Wait, then try again.",
        "Blocked by {integration} rate limits. Wait a moment and retry.",
    ),
    "tool_error.connector_timeout": (
        "{integration} did not respond in time. Try again shortly.",
        "{integration} timed out. Retry in a moment.",
        "No timely response from {integration}. Try again shortly.",
        "{integration} took too long to respond. Try again in a bit.",
        "Timeout talking to {integration}. Retry shortly.",
    ),
    "tool_error.tool_not_available": (
        "That tool is not Connected or permitted for this agent. Connect it at /connectors or switch mode.",
        "This tool is unavailable — not Connected or not permitted. Connect it at /connectors or switch mode.",
        "I cannot use that tool here (not Connected or not allowed). Connect at /connectors or change mode.",
        "Tool not available for this agent. Connect it at /connectors or switch mode.",
        "Blocked: tool not Connected or not permitted. Fix that at /connectors or switch mode.",
    ),
    "tool_error.action_not_found": (
        "This action is not implemented yet for {integration}.",
        "That action is not available for {integration} yet.",
        "{integration} does not implement this action yet.",
        "No implementation for this {integration} action yet.",
        "This {integration} action is not wired up yet.",
    ),
    "tool_error.tool_error": (
        "{integration} returned an error{action_suffix}. Check connector health at /connectors — it may not be Healthy.",
        "{integration} errored{action_suffix}. Check health at /connectors — it may not be Healthy.",
        "Error from {integration}{action_suffix}. Review connector health at /connectors (Healthy status).",
        "{integration} failed this call{action_suffix}. Check /connectors — it may not be Healthy.",
        "Blocked by a {integration} error{action_suffix}. Confirm it is Healthy at /connectors, then retry.",
    ),
    "tool_error.unverifiable_output": (
        "The connector action completed but returned no Verified output (missing body and result link).",
        "Action finished without Verified output — no body or result link came back.",
        "Completed, but nothing Verified was returned (missing body and result link).",
        "No Verified output from that run (body and result link missing).",
        "The run completed without Verifiable output — missing body and result link.",
    ),
}

VOICE_EXPRESSION_STATE_KEY = "voice_expression_last"

_voice_last_indices: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar(
    "gravitree_voice_expression_last", default=None
)
# Category → index chosen this turn (same category must not rotate mid-turn).
_voice_chosen_this_turn: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar(
    "gravitree_voice_expression_chosen", default=None
)
# Optional (conversation_id, org_id, client, settings) for persist after rotation.
_voice_persist_target: contextvars.ContextVar[
    tuple[str, str, Any, Any] | None
] = contextvars.ContextVar("gravitree_voice_expression_persist", default=None)


def next_variant_index(count: int, last_index: int | None) -> int:
    """Deterministic rotation: 0 when unset/invalid, else (last+1) % count."""
    if count <= 0:
        raise ValueError("variant bank must be non-empty")
    if last_index is None or last_index < 0 or last_index >= count:
        return 0
    return (last_index + 1) % count


def expression_excluded(category: str) -> bool:
    return str(category or "").strip().lower() in EXPRESSION_EXCLUDED


def bank_for(category: str) -> tuple[str, ...] | None:
    key = str(category or "").strip().lower()
    if not key or expression_excluded(key):
        return None
    return EXPRESSION_BANKS.get(key)


def bind_voice_expression_state(
    task_state: Mapping[str, Any] | None,
    *,
    reuse_if_bound: bool = False,
    conversation_id: str | None = None,
    org_id: str | None = None,
    client: Any = None,
    settings: Any = None,
) -> contextvars.Token | None:
    """Bind mutable last-index map from conversation task_state for this turn.

    When ``reuse_if_bound`` and a parent turn already bound state, returns None
    (caller must not reset). Optional conversation/org enable async persist after
    each rotation so ReAct/tool_error paths keep variety across turns.
    """
    if reuse_if_bound and _voice_last_indices.get() is not None:
        if conversation_id and org_id:
            _voice_persist_target.set((str(conversation_id), str(org_id), client, settings))
        return None
    raw: dict[str, int] = {}
    if isinstance(task_state, Mapping):
        existing = task_state.get(VOICE_EXPRESSION_STATE_KEY)
        if isinstance(existing, dict):
            for key, value in existing.items():
                try:
                    raw[str(key)] = int(value)
                except (TypeError, ValueError):
                    continue
    token = _voice_last_indices.set(raw)
    _voice_chosen_this_turn.set({})
    if conversation_id and org_id:
        _voice_persist_target.set((str(conversation_id), str(org_id), client, settings))
    else:
        _voice_persist_target.set(None)
    return token


def reset_voice_expression_state(token: contextvars.Token | None) -> None:
    if token is not None:
        _voice_last_indices.reset(token)
    _voice_chosen_this_turn.set(None)
    _voice_persist_target.set(None)


def _persist_voice_expression_sync() -> None:
    """Write voice_expression_last immediately so the next HTTP turn can rotate."""
    target = _voice_persist_target.get()
    state = _voice_last_indices.get()
    if not target or not isinstance(state, dict) or not state:
        return
    conversation_id, org_id, client, settings = target
    snap = dict(state)
    try:
        from app.config import get_settings
        from app.workflows.repository import get_supabase_client

        # Always use the sync service-role client — request-scoped clients may be
        # async wrappers that silently no-op on .execute().
        sb = get_supabase_client(settings or get_settings())
        rows = (
            sb.table("conversations")
            .select("task_state")
            .eq("id", conversation_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        current = {}
        if rows.data and isinstance(rows.data[0].get("task_state"), dict):
            current = dict(rows.data[0]["task_state"])
        current[VOICE_EXPRESSION_STATE_KEY] = snap
        sb.table("conversations").update({"task_state": current}).eq(
            "id", conversation_id
        ).eq("org_id", org_id).execute()
    except Exception:  # noqa: BLE001
        logger.warning(
            "voice_expression_last sync persist failed conversation_id=%s",
            conversation_id,
            exc_info=True,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _persist() -> None:
            try:
                from app.config import get_settings
                from app.services.conversation_state_service import get_conversation_state_service

                await get_conversation_state_service(settings or get_settings()).update_task_state(
                    conversation_id,
                    org_id,
                    {VOICE_EXPRESSION_STATE_KEY: snap},
                    client=client,
                )
            except Exception:  # noqa: BLE001
                logger.debug("voice_expression_last async persist failed", exc_info=True)

        loop.create_task(_persist())


def voice_expression_state_snapshot() -> dict[str, int]:
    current = _voice_last_indices.get()
    return dict(current) if isinstance(current, dict) else {}


def pick_expression(
    category: str,
    *,
    ctx: Mapping[str, Any] | None = None,
    force_index: int | None = None,
) -> str | None:
    """Format next (or forced) variant. Returns None if category has no bank / excluded.

    When a turn has bound ``voice_expression_last`` state, advances the index for
    ``category`` so the same conversation does not immediately repeat. Without
    bound state, always returns index 0 (stable for unit tests and one-off calls).
    """
    bank = bank_for(category)
    if not bank:
        return None
    state = _voice_last_indices.get()
    chosen = _voice_chosen_this_turn.get()
    if force_index is not None:
        idx = force_index % len(bank)
    elif state is None:
        idx = 0
    elif chosen is not None and category in chosen:
        # Same category asked twice in one turn — keep the same sentence.
        idx = chosen[category] % len(bank)
    else:
        idx = next_variant_index(len(bank), state.get(category))
        state[category] = idx
        if chosen is not None:
            chosen[category] = idx
        _persist_voice_expression_sync()
    template = bank[idx]
    if "{" not in template:
        return template
    safe = {k: ("" if v is None else v) for k, v in dict(ctx or {}).items()}
    try:
        return template.format(**safe)
    except KeyError:
        # Incomplete ctx — fall back to first variant with partial format.
        return bank[0].format(**{k: safe.get(k, "") for k in _format_keys(bank[0])})


def all_expressions(category: str, *, ctx: Mapping[str, Any] | None = None) -> list[str]:
    """Every variant for a category with the same ctx (for fact-consistency tests)."""
    bank = bank_for(category)
    if not bank:
        return []
    out: list[str] = []
    for i in range(len(bank)):
        text = pick_expression(category, ctx=ctx, force_index=i)
        if text:
            out.append(text)
    return out


def _format_keys(template: str) -> list[str]:
    return re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", template)


def assert_fact_tokens_consistent(
    variants: Sequence[str],
    required_tokens: Sequence[str],
) -> None:
    """Raise AssertionError if any variant is missing a required factual token."""
    if not variants:
        raise AssertionError("no variants to check")
    for token in required_tokens:
        needle = str(token)
        if not needle:
            continue
        missing = [v for v in variants if needle.lower() not in v.lower()]
        if missing:
            raise AssertionError(
                f"fact token {needle!r} missing from {len(missing)}/{len(variants)} variants; "
                f"example={missing[0]!r}"
            )
