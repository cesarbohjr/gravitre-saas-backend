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

from app.core.safe_dict import safe_normalize_stored_dict

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
    # --- Conversational path (priority: known identical-fallback gap) ---
    "conversational.greeting": (
        "Hey — what can I help you with?",
        "Good to see you. What are we working on?",
        "Hi — what's on your mind?",
        "Hey. What do you want to get done?",
        "Hello — where should we start?",
        "Morning. What are we working on?",
        "Hi — what do you need help with?",
    ),
    "conversational.small_talk": (
        "Doing well, thanks. What's on your mind?",
        "Good, thanks. What are we working on?",
        "Can't complain. What's going on?",
        "All good here. What do you need?",
        "Doing well. Where should we start?",
        "Doing fine. What should we tackle?",
        "All good on my end. How can I help?",
    ),
    "conversational.thanks": (
        "You're welcome.",
        "Glad to help.",
        "Anytime.",
        "You bet.",
        "Happy to.",
        "Of course.",
        "No problem.",
    ),
    "conversational.banter": (
        "Ha — fair.",
        "Fair enough.",
        "Okay, I deserved that one.",
        "Noted.",
        "Alright, fair.",
        "Point taken.",
        "Okay — I'm with you.",
    ),
    "conversational.venting": (
        "That's rough, especially with the clock running. What's the first thing you want to check?",
        "I hear you — that's a lot of pressure. Let's start with the most urgent piece.",
        "That's a tough spot. What's the first thing we need to get clear?",
        "Yeah, that's stressful with a deadline that close. Let's tackle the biggest blocker first.",
        "That sounds rough. We can work through it one piece at a time.",
        "Fair frustration. Let's start with the thing that's hurting most.",
        "That's a hard spot to be in. Tell me what needs attention first.",
    ),
    "conversational.meta_capability": (
        "I'm Gravitre. I can help you understand what's happening, work through a plan, and use your connected tools when you want to take action. {capability}",
        "I can help you think through the work and, when it makes sense, act through the tools connected to Gravitre. {capability}",
        "Think of me as the conversational layer across Gravitre — I can answer, plan, and take approved actions through your connected tools. {capability}",
        "I can help you figure something out or carry it through using the tools your workspace has connected. {capability}",
        "I work across your Gravitre workspace: answering questions, helping with plans, and taking actions through connected tools when they're approved. {capability}",
        "I can help with the thinking and the doing — from answering a question to using a connected tool when an action is ready to run. {capability}",
    ),
    "conversational.mixed_ack_banter": (
        "Ha — noted.",
        "Fair enough.",
        "Got it.",
        "Noted.",
        "Alright.",
        "Okay — on the task.",
    ),
    "conversational.mixed_ack_thanks": (
        "You're welcome.",
        "Glad to.",
        "Anytime.",
        "You bet.",
        "Happy to.",
    ),
    "conversational.mixed_ack_greeting": (
        "Hey — got it.",
        "Hi — got it.",
        "Got it.",
        "Yep — I'm with you.",
        "Sure — I can help with that.",
    ),
    "connector_connect_to_run": (
        "Connect {integration} in Settings → Connectors and I can run this.",
        "This needs {integration}, and it isn't connected yet. Hook it up in Settings → Connectors, then try again.",
        "I can't reach {integration} because it isn't connected. Connect it in Settings → Connectors and I'll pick this back up.",
        "{integration} isn't connected for your team yet. Open Settings → Connectors, connect it, and try again.",
        "I'll need {integration} for this. Once it's connected in Settings → Connectors, I can run it.",
        "{integration} isn't set up yet. Finish connecting it in Settings → Connectors, then ask me again.",
    ),
    "skipped_connector": (
        "Skipped this step because {integration} isn't connected.",
        "I skipped this one since {integration} isn't connected yet.",
        "I couldn't do this step. {integration} isn't connected.",
        "I passed on this step because {integration} isn't hooked up yet.",
        "This step got skipped since {integration} isn't connected for your team.",
    ),
    "insufficient_info": (
        "I don't have enough to go on yet. Tell me what's missing and I'll keep going.",
        "I'm missing a detail I need. Share it and I'll carry on.",
        "Not quite enough to go on yet. Give me the missing piece and I'll continue.",
        "I just need one more detail. Send it over and I'll keep going.",
        "I'm stuck without one more detail. Fill me in and I'll pick it back up.",
        "I can't finish with what I've got. Tell me what's missing and I'll take it from there.",
    ),
    "assumption_flag": (
        "I'm assuming this based on the tools you've connected so far, so tell me if that's wrong.",
        "This is my best guess from what's connected so far. Correct me if it's off.",
        "I'm working from what's connected so far, so let me know if that's off.",
        "I've inferred this from your connected tools. Say if I should use something else.",
        "That's an assumption based on what I can see so far. Push back if it's wrong.",
    ),
    "success_win": (
        "Done, and I checked that it worked.",
        "Finished. I double-checked the result.",
        "All done, and I confirmed it worked.",
        "That's finished, and I've confirmed the result.",
        "All set. I checked, and it's there.",
        "Done. It checks out.",
    ),
    "success_win_light": (
        "Done — clean run.",
        "Finished — clean run.",
        "That one landed cleanly.",
        "Clean run — done.",
        "All clear — clean run.",
    ),
    "blocked_generic": (
        "I'm stuck on this one. {blocker} To get it moving: {next_action}",
        "I can't go further yet. {blocker} What would help: {next_action}",
        "This is on hold for now. {blocker} {next_action}",
        "I hit a snag. {blocker} {next_action}",
        "I couldn't get past this. {blocker} Next step: {next_action}",
        "I'm held up here. {blocker} To sort it out: {next_action}",
    ),
    "skipped_unsupported": (
        "Skipped this step because I don't have a way to do it yet.",
        "I skipped this one. There's nothing I can use to do it yet.",
        "I couldn't find a way to do this step, so I skipped it.",
        "This step got skipped since nothing I have can handle it.",
        "I passed on this step. None of your tools can do it yet.",
    ),
    "no_executable_action": (
        "I don't have a way to do that yet.",
        "I couldn't find anything I can run for that.",
        "None of your connected tools can do that yet.",
        "That's not something I can do with what's set up right now.",
        "I don't have anything that handles that request yet.",
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
        "Estimate — based on what's connected so far:",
        "Estimate from what's connected so far:",
        "Estimate (just from your connected tools):",
        "Estimate — going only on what's connected:",
        "Rough estimate from what's connected so far:",
    ),
    "missing_parameters_header": (
        "Still needed:",
        "I still need:",
        "Missing before I can continue:",
        "To proceed I still need:",
        "Outstanding details:",
        "Not yet filled in:",
    ),
    # tool_error codes (same facts: integration, Settings → Connectors, action_suffix)
    "tool_error.auth_expired": (
        "Your {integration} sign-in expired. Reconnect it in Settings → Connectors, then try again.",
        "{integration} signed me out. Reconnect it in Settings → Connectors and try again.",
        "The {integration} sign-in has expired. Reconnect it in Settings → Connectors and we can try again.",
        "{integration} needs a quick reconnect because the sign-in expired. You can do that in Settings → Connectors.",
        "I lost access to {integration} because the sign-in expired. Reconnect it in Settings → Connectors, then try again.",
        "{integration} isn't signed in anymore. Reconnect it in Settings → Connectors, then try again.",
    ),
    "tool_error.permission_denied": (
        "You don't have permission to do this{action_suffix}. Ask an admin for access, or we can try a different tool.",
        "Your role doesn't allow this{action_suffix}. An admin can give you access, or we can use another tool.",
        "You aren't allowed to do this yet{action_suffix}. Ask an admin for access, or pick a different tool.",
        "This{action_suffix} needs permission you don't have. Ask an admin, or we can use a different tool.",
        "I can't do this for you{action_suffix} because you don't have access. An admin can fix that, or we can switch tools.",
    ),
    "tool_error.connector_not_connected": (
        "{integration} isn't connected yet. Connect it in Settings → Connectors, or reply **yes** and I'll open the setup, then try again.",
        "{integration} isn't connected here. Connect it in Settings → Connectors (or reply **yes** to start the setup), then try again.",
        "You haven't connected {integration} yet. Open Settings → Connectors or reply **yes** to connect it, then try again.",
        "I can't use {integration} because it isn't connected. Connect it in Settings → Connectors or reply **yes**, then try again.",
        "{integration} isn't connected for your team yet. Set it up in Settings → Connectors (reply **yes** to start), then try again.",
        "I'll need {integration} connected first. Head to Settings → Connectors or say **yes** to start the setup, then try again.",
    ),
    "tool_error.channel_not_found": (
        "That Slack channel was not found (or the bot is not a member). Use a public channel name/id the bot can access, invite the bot, then try again.",
        "Slack channel missing or the bot is not a member. Pick a public channel the bot can access, invite it, then retry.",
        "I could not find that Slack channel (or the bot is not in it). Use a reachable public channel, invite the bot, then try again.",
        "Channel not found for Slack — or the bot is not a member. Correct the channel, invite the bot, then retry.",
        "That Slack channel is unavailable to the bot. Use a public channel it can access, invite it, then try again.",
    ),
    "tool_error.missing_scope": (
        "{integration} is connected but doesn't have the permissions this needs{action_suffix}. Reconnect it in Settings → Connectors and approve the extra access.",
        "{integration} is connected, but it's missing some access{action_suffix}. Reconnect it in Settings → Connectors and approve what it asks for.",
        "Your {integration} connection needs a bit more access{action_suffix}. Reconnect it in Settings → Connectors and grant it.",
        "{integration} needs extra permissions{action_suffix}. Reconnect it in Settings → Connectors, approve them, then try again.",
        "I can reach {integration}, but not with enough access{action_suffix}. Reconnect it in Settings → Connectors and approve the extra permissions.",
    ),
    "tool_error.validation_error": (
        "{integration} didn't accept that{action_suffix}. Check the required details and try again.",
        "Some details are missing or off for {integration}{action_suffix}. Fix them up and try again.",
        "{integration} turned that down{action_suffix}. Double-check the required details and try again.",
        "{integration} needs a couple of details fixed first{action_suffix}. Correct them, then try again.",
        "That didn't go through in {integration}{action_suffix} because something's missing or wrong. Have a look and try again.",
    ),
    "tool_error.rate_limited": (
        "{integration} is getting too many requests right now. Give it a moment and try again.",
        "{integration} asked me to slow down. Let's wait a moment, then try again.",
        "We hit {integration}'s limit for the moment. Wait a bit and try again.",
        "{integration} needs a short break from requests. Try again in a moment.",
        "Too many requests to {integration} at once. Give it a minute and try again.",
    ),
    "tool_error.connector_timeout": (
        "{integration} didn't answer in time. Try again shortly.",
        "{integration} took too long. Let's try again in a moment.",
        "I didn't hear back from {integration} in time. Try again shortly.",
        "{integration} was too slow to respond. Try again in a bit.",
        "{integration} timed out on me. Let's give it another go shortly.",
    ),
    "tool_error.tool_not_available": (
        "That tool isn't connected or isn't allowed here. Connect it in Settings → Connectors or switch modes.",
        "I can't use that tool right now because it isn't connected or allowed. Connect it in Settings → Connectors or switch modes.",
        "That tool isn't available to me here. You can connect it in Settings → Connectors or change modes.",
        "I don't have that tool in this mode. Connect it in Settings → Connectors or switch modes.",
        "That tool isn't set up for me here. Fix that in Settings → Connectors or switch modes.",
    ),
    "tool_error.action_not_found": (
        "I can't do that in {integration} yet.",
        "That isn't something I can do in {integration} yet.",
        "{integration} doesn't support that through me yet.",
        "I don't have a way to do that in {integration} yet.",
        "That's not set up for {integration} yet.",
    ),
    "tool_error.tool_error": (
        "{integration} ran into a problem{action_suffix}. Check that it's still working in Settings → Connectors, then try again.",
        "Something went wrong on {integration}'s side{action_suffix}. Make sure it's still connected in Settings → Connectors.",
        "{integration} hit an error{action_suffix}. Take a look at it in Settings → Connectors, then try again.",
        "That didn't work in {integration}{action_suffix}. Check Settings → Connectors to make sure it's still working.",
        "{integration} gave me an error{action_suffix}. Check it in Settings → Connectors, then try again.",
    ),
    "tool_error.unverifiable_output": (
        "That finished, but nothing came back that I could check, so I can't confirm the result.",
        "It ran, but I didn't get anything back to confirm it worked.",
        "That ran, but there wasn't anything I could check, so I can't confirm it.",
        "It ran, but I got nothing back to show for it, so I can't confirm the result.",
        "That wrapped up without a result I could look at, so I can't say for sure it worked.",
    ),
}

VOICE_EXPRESSION_STATE_KEY = "voice_expression_last"

_voice_last_indices: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar(
    "gravitre_voice_expression_last", default=None
)
# Category → index chosen this turn (same category must not rotate mid-turn).
_voice_chosen_this_turn: contextvars.ContextVar[dict[str, int] | None] = contextvars.ContextVar(
    "gravitre_voice_expression_chosen", default=None
)
# Optional (conversation_id, org_id, client, settings) for persist after rotation.
_voice_persist_target: contextvars.ContextVar[
    tuple[str, str, Any, Any] | None
] = contextvars.ContextVar("gravitre_voice_expression_persist", default=None)


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
    from app.services.speculative_execution import current_scope

    scope = current_scope()
    if scope is not None:
        # Speculative (unconfirmed) voice run: same patch, applied only on adoption.
        def _deferred_patch():
            from app.config import get_settings
            from app.services.conversation_state_service import get_conversation_state_service

            return get_conversation_state_service(settings or get_settings()).update_task_state(
                conversation_id, org_id, {VOICE_EXPRESSION_STATE_KEY: snap}, client=client
            )

        scope.defer("voice.expression_rotation", _deferred_patch)
        return
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
        if rows.data:
            current = safe_normalize_stored_dict(rows.data[0], key="task_state")
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
