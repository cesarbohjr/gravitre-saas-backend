"""Name resolution v2: the Gmail lookup on a noisy mailbox, its coverage
and account rules, cached-candidate revalidation, and "Send Stephanie the
budget spreadsheet" on both surfaces.

All mail, people and files are invented fixtures; no real account is read.
"""
from __future__ import annotations

from typing import Any

import pytest

import app.services.recipient_resolution as rr
from app.services.recipient_resolution import (
    resolution_question,
    resolve_email_recipient,
)
from tests.scenarios.conversation_harness import (
    ORG,
    USER,
    BrainCall,
    Reply,
    ScenarioHarness,
    TurnResult,
)
from tests.scenarios.name_resolution_fixtures import (
    NOISY_EXPECTATIONS,
    budget_files,
    busy_mailbox,
    gmail_rows_for_two_accounts,
    mail,
    noisy_mailbox,
    one_budget_file,
)

SURFACES = ("text", "voice")
READS = {
    "gmail.messages.list",
    "gmail.messages.get",
    "google_drive.search_files",
    "drive.search_files",
    "google_drive.get_file_metadata",
    "drive.get_file_metadata",
}
ME = "Me <me@gravitre.example>"
KHAN = "Stephanie Khan <stephanie.khan@acme.example>"
MILLER = "Stephanie Miller <smiller@globex.example>"


async def _lookup(h: ScenarioHarness, name: str, **kw: Any) -> rr.RecipientResolution:
    return await resolve_email_recipient(
        name,
        org_id=ORG,
        client=h.db,
        settings=h.settings,
        connected_integrations=["gmail"],
        user_id=USER,
        **kw,
    )


# --- the Gmail lookup on a realistic noisy mailbox ---------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(("query", "status", "addresses"), NOISY_EXPECTATIONS)
async def test_noisy_mailbox_outcomes(query: str, status: str, addresses: list[str]) -> None:
    with ScenarioHarness() as h:
        h.connectors.mailbox += noisy_mailbox()
        res = await _lookup(h, query)
        assert res.status == status, (res.status, res.reason, [c.address for c in res.candidates])
        assert [c.address for c in res.candidates] == addresses
        assert res.coverage["complete"] is True
        assert all(c.action in READS for c in h.connectors.calls), "discovery wrote something"
        # Only headers are read, never bodies.
        gets = [c for c in h.connectors.calls if c.action == "gmail.messages.get"]
        assert all(c.params.get("format") == "metadata" for c in gets)


@pytest.mark.asyncio
async def test_noise_is_counted_not_offered() -> None:
    with ScenarioHarness() as h:
        h.connectors.mailbox += noisy_mailbox()
        res = await _lookup(h, "Stephanie")
        excluded = res.coverage["excluded"]
        assert excluded["own"] >= 1  # the user is a Stephanie herself
        assert excluded["no_reply"] == 2
        assert excluded["list_relay"] == 1
        assert excluded["bulk_only"] == 1  # the marketing sender left in the inbox
        offered = {c.address for c in res.candidates}
        assert not offered & {
            "stephanie.lane@gravitre.example",
            "stephanie@brand.example",
            "hello@acmeweekly.example",
            "comments-noreply@docs.example",
            "notifications@tracker.example",
            "team@lists.acme.example",
        }
        # The query itself keeps promotions and social mail out.
        listed = next(c for c in h.connectors.calls if c.action == "gmail.messages.list")
        assert "-category:promotions" in listed.params["q"] and "-category:social" in listed.params["q"]


@pytest.mark.asyncio
async def test_full_name_query_is_a_phrase_on_from_to_and_cc() -> None:
    with ScenarioHarness() as h:
        h.connectors.mailbox += noisy_mailbox()
        await _lookup(h, "Stephanie Wu")
        q = next(c for c in h.connectors.calls if c.action == "gmail.messages.list").params["q"]
        assert q.startswith('(from:"Stephanie Wu" OR to:"Stephanie Wu" OR cc:"Stephanie Wu")')


def test_a_draft_only_match_is_offered_for_confirmation_never_resolved() -> None:
    res = rr.RecipientResolution(
        status="ambiguous",
        query="Stephanie Park",
        candidates=[rr.RecipientCandidate(name="Stephanie Park", address="spark@initech.example", source="gmail")],
        reason="draft_only",
    )
    assert resolution_question(res) == (
        "The only Stephanie Park I found is spark@initech.example, and only in an unsent draft, "
        "so I can't confirm it. Should I use that address?"
    )
    assert rr.pick_candidate("Yes, that one.", res.candidates).address == "spark@initech.example"


# --- coverage: pages, caps, time --------------------------------------------


@pytest.mark.asyncio
async def test_pages_are_followed_until_the_matches_run_out() -> None:
    with ScenarioHarness() as h:
        h.connectors.mailbox += busy_mailbox(khan_messages=40)
        res = await _lookup(h, "Stephanie")
        lists = [c for c in h.connectors.calls if c.action == "gmail.messages.list"]
        assert len(lists) == 2 and lists[1].params.get("page_token") == "25"
        assert res.coverage["complete"] is True and res.coverage["pages"] == 2
        # Wu is in the oldest mail, on the second page.
        assert res.status == "ambiguous"
        assert {c.address for c in res.candidates} == {"stephanie.khan@acme.example", "swu@globex.example"}


@pytest.mark.asyncio
async def test_a_page_cap_makes_one_match_incomplete_not_unique() -> None:
    with ScenarioHarness() as h:
        h.connectors.mailbox += busy_mailbox(khan_messages=80)
        res = await _lookup(h, "Stephanie")
        assert res.status == "incomplete", "a capped search declared a unique match"
        assert res.reason == "message_cap"
        assert [c.address for c in res.candidates] == ["stephanie.khan@acme.example"]
        assert res.coverage["messages_read"] == rr.MAX_MESSAGES
        assert len([c for c in h.connectors.calls if c.action == "gmail.messages.list"]) <= rr.MAX_PAGES
        question = resolution_question(res)
        assert question == (
            "I found Stephanie Khan (stephanie.khan@acme.example), but I couldn't check all of your mail, "
            "so there may be another Stephanie. Is that who you mean?"
        )
        # A more precise query finds the one the capped search could not reach.
        precise = await _lookup(h, "Stephanie Wu")
        assert precise.status == "resolved" and precise.chosen.address == "swu@globex.example"


@pytest.mark.asyncio
async def test_the_time_budget_stops_the_search_and_says_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rr, "LOOKUP_BUDGET_S", 0.35)
    with ScenarioHarness() as h:
        h.connectors.mailbox += busy_mailbox(khan_messages=30)
        h.connectors.read_latency_s = 0.12
        res = await _lookup(h, "Stephanie")
        assert res.status in {"incomplete", "unavailable"}
        assert res.status != "resolved"
        if res.status == "incomplete":
            assert res.reason == "time_budget"


@pytest.mark.asyncio
async def test_no_match_with_pages_left_is_incomplete_not_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rr, "MAX_PAGES", 1)
    with ScenarioHarness() as h:
        # 30 hits for the name, all from a no-reply sender: page one holds 25.
        h.connectors.mailbox += [mail(i, "Jordan Bot <no-reply@bot.example>", ME) for i in range(30)]
        res = await _lookup(h, "Jordan")
        assert res.status == "incomplete" and not res.candidates
        assert resolution_question(res).startswith("I couldn't find Jordan in the part of your Gmail I could check.")


@pytest.mark.asyncio
async def test_a_permission_failure_is_unavailable_and_says_so() -> None:
    with ScenarioHarness() as h:
        h.connectors.mailbox += noisy_mailbox()
        h.connectors.fail["gmail.messages.list"] = "permission_denied"
        res = await _lookup(h, "Stephanie")
        assert res.status == "unavailable" and res.reason == "permission"
        assert resolution_question(res).startswith("I don't have permission to read your Gmail right now")


# --- explicit account selection ---------------------------------------------


@pytest.mark.asyncio
async def test_the_default_account_is_searched_and_recorded() -> None:
    from app.services.object_resolution import connected_accounts, select_account

    with ScenarioHarness() as h:
        h.db.tables["connectors"] = gmail_rows_for_two_accounts()
        h.connectors.mailbox += noisy_mailbox()
        accounts = connected_accounts(h.db, ORG, "gmail")
        assert [a.id for a in accounts] == ["gmail-work", "gmail-home"]
        account, how = select_account(accounts, "Send an email to Stephanie Wu")
        assert (account.id, how) == ("gmail-work", "default")
        res = await _lookup(h, "Stephanie Wu", account=account)
        assert res.chosen.account == "gmail-work"
        assert res.chosen.account_label == "stephanie.lane@gravitre.example"
        assert res.chosen.account_stamp == "2026-10-10T09:00:00+00:00"
        assert res.accounts == ["stephanie.lane@gravitre.example"]
        reads = [c for c in h.connectors.calls if c.action.startswith("gmail.")]
        assert reads and all(c.params.get("connector_id") == "gmail-work" for c in reads)


def test_a_named_account_is_the_one_searched() -> None:
    from app.services.object_resolution import Account, select_account

    accounts = [
        Account(id="gmail-work", vendor="gmail", label="stephanie.lane@gravitre.example", emails=("stephanie.lane@gravitre.example",)),
        Account(id="gmail-home", vendor="gmail", label="steph.lane@home.example", emails=("steph.lane@home.example",)),
    ]
    account, how = select_account(accounts, "Email Stephanie Wu from steph.lane@home.example")
    assert (account.id, how) == ("gmail-home", "named")
    assert rr.extract_recipient_name(rr._strip_account_addresses("Email Stephanie Wu from steph.lane@home.example", accounts)) == "Stephanie Wu"


# --- conversations ------------------------------------------------------------


def _guessing_model(call: BrainCall) -> Reply:
    """A model that fills in an address nobody gave it.

    When the send tool was only offered by name, the first call loads its
    schema; like a real model, it then calls the tool again.
    """
    tool_results = [m for m in call.messages if m.get("role") == "tool"]
    schema_loaded = bool(tool_results) and '"loaded"' in str(tool_results[-1].get("content") or "")
    if call.after_tool and not schema_loaded:
        return Reply(text="Done.")
    name = next((t for t in call.tool_names if "gmail" in t and "send" in t), None)
    if name:
        return Reply(tool_calls=[(name, {"to": "stephanie@invented.example"})])
    return Reply(text="Who should it go to?")


def _args(turn: TurnResult) -> dict[str, Any]:
    return dict(((turn.pending_task or {}).get("params") or {}).get("args") or {})


def _only_reads(turn: TurnResult) -> bool:
    return all(c.action in READS for c in turn.connector_calls)


def _age_state(h: ScenarioHarness, key: str, seconds: float) -> None:
    for row in h.db.tables.get("conversations", []):
        state = row.get("task_state") or {}
        if key == rr.CANDIDATES_KEY:
            for cand in state.get(key) or []:
                cand["resolved_at"] = float(cand.get("resolved_at") or 0) - seconds


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_noisy_mailbox_conversation_asks_once_then_sends_to_the_choice(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        h.connectors.mailbox += noisy_mailbox()
        conv = h.conversation(surface)

        asked = await conv.say("Send an email to Stephanie on Gmail", _guessing_model)
        assert asked.text == (
            "I found four Stephanies: Stephanie Wu, Stephanie Khan at acme.example, "
            "Stephanie Khan at gmail.example, and Stephanie Park. Which one?"
        )
        assert "to" not in _args(asked)
        assert _only_reads(asked)

        chosen = await conv.say("Wu", "Okay.")
        assert _args(chosen)["to"] == "swu@globex.example"
        assert chosen.text == "Got it, Stephanie Wu. What would you like to say?"
        assert not [c for c in chosen.connector_calls if c.action not in READS]


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_stale_candidates_are_looked_up_again_before_use(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",)), mail(3, MILLER, ME)]
        conv = h.conversation(surface)
        await conv.say("Send an email to Stephanie on Gmail", _guessing_model)
        _age_state(h, rr.CANDIDATES_KEY, rr.CANDIDATE_TTL_S + 60)

        chosen = await conv.say("Khan", "Okay.")
        assert any(c.action == "gmail.messages.list" for c in chosen.connector_calls), "stale candidates reused"
        assert _args(chosen)["to"] == "stephanie.khan@acme.example"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_a_reconnected_account_invalidates_cached_candidates(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        h.db.tables["connectors"] = gmail_rows_for_two_accounts()
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",)), mail(3, MILLER, ME)]
        conv = h.conversation(surface)
        asked = await conv.say("Send an email to Stephanie on Gmail", _guessing_model)
        stored = asked.task_state.get(rr.CANDIDATES_KEY) or []
        assert stored and all(c["account"] == "gmail-work" for c in stored)
        # The work account is reconnected between the question and the answer.
        h.db.tables["connectors"][0]["updated_at"] = "2026-10-11T08:00:00+00:00"

        chosen = await conv.say("Khan", "Okay.")
        assert any(c.action == "gmail.messages.list" for c in chosen.connector_calls)
        assert _args(chosen)["to"] == "stephanie.khan@acme.example"
        assert _args(chosen)["connector_id"] == "gmail-work"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_a_permission_failure_drops_cached_candidates_and_asks_for_the_address(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",)), mail(3, MILLER, ME)]
        conv = h.conversation(surface)
        await conv.say("Send an email to Stephanie on Gmail", _guessing_model)
        _age_state(h, rr.CANDIDATES_KEY, rr.CANDIDATE_TTL_S + 60)
        h.connectors.fail["gmail.messages.list"] = "permission_denied"

        again = await conv.say("Stephanie Khan", "Okay.")
        assert "to" not in _args(again)
        assert again.text.startswith("I don't have permission to read your Gmail right now")
        assert not again.task_state.get(rr.CANDIDATES_KEY)


# --- "Send Stephanie the budget spreadsheet" ----------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_send_stephanie_the_budget_spreadsheet_end_to_end(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected += ["gmail", "google_drive"]
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",))]
        h.connectors.files += budget_files()
        conv = h.conversation(surface)

        first = await conv.say("Send Stephanie the budget spreadsheet", _guessing_model)
        assert first.text == (
            "I found Stephanie Khan in your Gmail correspondence. "
            'I found two files that match "budget spreadsheet": Budget 2026 (in Finance, modified Oct 3, 2026) '
            "and Budget 2026 (in Drafts, modified Sep 12, 2026). Which one?"
        )
        assert _args(first)["to"] == "stephanie.khan@acme.example"
        assert "file_id" not in _args(first), "an ambiguous file was chosen silently"
        assert _only_reads(first)

        picked = await conv.say("The Finance one.", "Okay.")
        assert picked.text == (
            "Got it, Budget 2026. I can't attach files to emails from here yet, so I'll add a link to it; "
            "the recipient needs access to open it. What would you like to say?"
        )
        args = _args(picked)
        assert args["file_id"] == "f-budget-finance" and args["file_source"] == "google_drive"
        assert "subject" not in args, "the file choice was used as the subject"
        # Access was checked with a metadata read before anything was staged.
        assert any(c.action.endswith("get_file_metadata") and c.params["file_id"] == "f-budget-finance" for c in picked.connector_calls)

        await conv.say("Here are the numbers for next year.", "Okay.")
        staged = await conv.say("The subject is Budget.", "Okay.")
        assert (staged.pending_task or {}).get("status") == "awaiting_confirm", staged.text
        assert "stephanie.khan@acme.example" in staged.text
        assert "Budget 2026 on Google Drive, added as a link (attachments aren't supported yet)" in staged.text
        assert _args(staged)["file_id"] == "f-budget-finance"

        sent = await conv.say("Yes, send it.", "Okay.")
        sends = [c for c in sent.connector_calls if c.action == "gmail.messages.send"]
        assert len(sends) == 1
        assert sends[0].params["to"] == "stephanie.khan@acme.example"
        assert sends[0].params["file_id"] == "f-budget-finance"
        # Checked again right before sending.
        idx = next(i for i, c in enumerate(sent.connector_calls) if c.action == "gmail.messages.send")
        assert any(c.action.endswith("get_file_metadata") for c in sent.connector_calls[:idx])


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_two_ambiguities_get_one_question_each(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected += ["gmail", "google_drive"]
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",)), mail(3, MILLER, ME)]
        h.connectors.files += budget_files()
        conv = h.conversation(surface)

        first = await conv.say("Send Stephanie the budget spreadsheet", _guessing_model)
        assert first.text == "I found two Stephanies: Stephanie Khan and Stephanie Miller. Which one?"

        second = await conv.say("Khan", "Okay.")
        assert second.text == (
            "Got it, Stephanie Khan. "
            'I found two files that match "budget spreadsheet": Budget 2026 (in Finance, modified Oct 3, 2026) '
            "and Budget 2026 (in Drafts, modified Sep 12, 2026). Which one?"
        )
        assert _args(second)["to"] == "stephanie.khan@acme.example"

        third = await conv.say("The second one", "Okay.")
        assert _args(third)["file_id"] == "f-budget-draft"
        assert third.text.endswith("What would you like to say?")


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_one_file_is_found_checked_and_carried_by_id(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected += ["gmail", "google_drive"]
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",))]
        h.connectors.files += one_budget_file()
        conv = h.conversation(surface)

        first = await conv.say("Send Stephanie the budget spreadsheet", _guessing_model)
        assert first.text == (
            "I found Stephanie Khan in your Gmail correspondence. I found Budget 2026 on Google Drive. "
            "I can't attach files to emails from here yet, so I'll add a link to it; the recipient needs access "
            "to open it. What would you like to say?"
        )
        assert _args(first)["file_id"] == "f-budget-finance"
        assert _args(first)["file_link"] == "https://docs.example/spreadsheets/f-budget-finance"


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_a_file_that_cannot_be_opened_is_not_carried(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected += ["gmail", "google_drive"]
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",))]
        files = one_budget_file()
        files[0]["denied"] = True
        h.connectors.files += files
        conv = h.conversation(surface)

        first = await conv.say("Send Stephanie the budget spreadsheet", _guessing_model)
        assert "file_id" not in _args(first)
        assert "I don't have permission to search your files right now, so I can't include it." in first.text


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_no_file_source_says_it_cannot_search_files_yet(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected.append("gmail")
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",))]
        conv = h.conversation(surface)

        first = await conv.say("Send Stephanie the budget spreadsheet", _guessing_model)
        assert "I can't search your files from here yet, so I can't include it." in first.text
        assert _args(first)["to"] == "stephanie.khan@acme.example"
        assert "file_id" not in _args(first)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", SURFACES)
async def test_a_file_access_lost_after_approval_stops_the_send(surface: str) -> None:
    with ScenarioHarness() as h:
        h.connected += ["gmail", "google_drive"]
        h.connectors.mailbox += [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",))]
        h.connectors.files += one_budget_file()
        conv = h.conversation(surface)

        await conv.say("Send Stephanie the budget spreadsheet", _guessing_model)
        await conv.say("Here are the numbers for next year.", "Okay.")
        staged = await conv.say("The subject is Budget.", "Okay.")
        assert (staged.pending_task or {}).get("status") == "awaiting_confirm", staged.text

        h.connectors.files[0]["denied"] = True
        sent = await conv.say("Yes, send it.", "Okay.")
        assert not [c for c in sent.connector_calls if c.action == "gmail.messages.send"], "sent without the file"
        assert "Nothing was sent" in sent.text or "didn't send" in sent.text
