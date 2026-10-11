"""Measure name resolution in the scenario harness (fixtures only).

Run from ``backend/``::

    python -m tests.scenarios.measure_name_resolution

Prints markdown: accuracy over the fixture set, clarification counts per
conversation, and lookup reads and latency with a simulated per-read
latency. Nothing here reaches a real account.
"""
from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any

import app.services.recipient_resolution as rr
from app.services.object_resolution import FileRequest, resolve_file
from tests.scenarios.conversation_harness import (
    ORG,
    USER,
    BrainCall,
    Reply,
    ScenarioHarness,
)
from tests.scenarios.name_resolution_fixtures import (
    NOISY_EXPECTATIONS,
    budget_files,
    busy_mailbox,
    mail,
    noisy_mailbox,
    one_budget_file,
)

ME = "Me <me@gravitre.example>"
KHAN = "Stephanie Khan <stephanie.khan@acme.example>"
MILLER = "Stephanie Miller <smiller@globex.example>"
SIMULATED_READ_S = 0.15


def _model(call: BrainCall) -> Reply:
    tool_results = [m for m in call.messages if m.get("role") == "tool"]
    loaded = bool(tool_results) and '"loaded"' in str(tool_results[-1].get("content") or "")
    if call.after_tool and not loaded:
        return Reply(text="Done.")
    name = next((t for t in call.tool_names if "gmail" in t and "send" in t), None)
    if name:
        return Reply(tool_calls=[(name, {"to": "stephanie@invented.example"})])
    return Reply(text="Who should it go to?")


async def _gmail(h: ScenarioHarness, name: str) -> rr.RecipientResolution:
    return await rr.resolve_email_recipient(
        name, org_id=ORG, client=h.db, settings=h.settings, connected_integrations=["gmail"], user_id=USER
    )


async def gmail_accuracy(latency: float) -> list[dict[str, Any]]:
    cases: list[tuple[str, list[dict[str, Any]], str, str, list[str]]] = [
        ("noisy", noisy_mailbox(), q, status, addrs) for q, status, addrs in NOISY_EXPECTATIONS
    ]
    cases += [
        ("busy (82 hits)", busy_mailbox(80), "Stephanie", "incomplete", ["stephanie.khan@acme.example"]),
        ("busy (82 hits)", busy_mailbox(80), "Stephanie Wu", "resolved", ["swu@globex.example"]),
        ("busy (42 hits)", busy_mailbox(40), "Stephanie", "ambiguous", ["stephanie.khan@acme.example", "swu@globex.example"]),
    ]
    rows = []
    for label, box, query, status, addrs in cases:
        with ScenarioHarness() as h:
            h.connectors.mailbox += box
            h.connectors.read_latency_s = latency
            started = time.perf_counter()
            res = await _gmail(h, query)
            wall = (time.perf_counter() - started) * 1000
            got = [c.address for c in res.candidates]
            rows.append(
                {
                    "mailbox": label,
                    "query": query,
                    "expected": status,
                    "got": res.status,
                    "ok": res.status == status and sorted(got) == sorted(addrs),
                    "calls": res.calls,
                    "ms": round(wall),
                    "pages": res.coverage.get("pages", 0),
                }
            )
    return rows


async def file_accuracy() -> list[dict[str, Any]]:
    cases = [
        ("two same-named sheets", budget_files(), FileRequest("budget spreadsheet", "budget", "spreadsheet"), "ambiguous", 2),
        ("one sheet", one_budget_file(), FileRequest("budget spreadsheet", "budget", "spreadsheet"), "resolved", 1),
        ("doc, not sheet", budget_files(), FileRequest("budget doc", "budget", "document"), "resolved", 1),
        ("content-only match", budget_files(), FileRequest("Q3 spreadsheet", "Q3", "spreadsheet"), "not_found", 0),
        ("no such file", budget_files(), FileRequest("pricing pdf", "pricing", "pdf"), "not_found", 0),
    ]
    rows = []
    for label, files, req, status, count in cases:
        with ScenarioHarness() as h:
            h.connectors.files += files
            res = await resolve_file(req, org_id=ORG, client=h.db, settings=h.settings, connected=["google_drive"])
            rows.append({"case": label, "expected": status, "got": res.status, "ok": res.status == status and len(res.candidates) == count, "calls": res.calls})
    with ScenarioHarness() as h:
        res = await resolve_file(FileRequest("budget spreadsheet", "budget", "spreadsheet"), org_id=ORG, client=h.db, settings=h.settings, connected=["gmail"])
        rows.append({"case": "no file source connected", "expected": "unavailable", "got": res.status, "ok": res.status == "unavailable", "calls": res.calls})
    return rows


_QUESTION_MARKERS = ("Which one?", "Is that who you mean?", "Should I use that address?", "Is that the one?", "What is it called?", "do you have the email address", "What's the email address?")


async def conversations(latency: float) -> list[dict[str, Any]]:
    flows: list[tuple[str, list[str], dict[str, Any], str]] = [
        ("one Stephanie", ["Send an email to Stephanie on Gmail", "Tell her the proposal is ready for review.", "The subject is Proposal."], {"mailbox": [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",))]}, "stephanie.khan@acme.example"),
        ("noisy mailbox, pick Wu", ["Send an email to Stephanie on Gmail", "Wu", "Tell her the contract is signed.", "The subject is Contract."], {"mailbox": noisy_mailbox()}, "swu@globex.example"),
        ("budget sheet, two files", ["Send Stephanie the budget spreadsheet", "The Finance one.", "Here are the numbers for next year.", "The subject is Budget."], {"mailbox": [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",))], "files": budget_files()}, "stephanie.khan@acme.example"),
        ("budget sheet, two Stephanies and two files", ["Send Stephanie the budget spreadsheet", "Khan", "The first one", "Here are the numbers for next year.", "The subject is Budget."], {"mailbox": [mail(1, KHAN, ME), mail(2, ME, KHAN, ("SENT",)), mail(3, MILLER, ME)], "files": budget_files()}, "stephanie.khan@acme.example"),
    ]
    out = []
    for surface in ("text", "voice"):
        for label, turns, data, expected_to in flows:
            with ScenarioHarness() as h:
                h.connected += ["gmail", "google_drive"]
                h.connectors.mailbox += data.get("mailbox", [])
                h.connectors.files += data.get("files", [])
                h.connectors.read_latency_s = latency
                conv = h.conversation(surface)
                questions = 0
                reads = 0
                turn_ms: list[float] = []
                last = None
                for i, text in enumerate(turns):
                    started = time.perf_counter()
                    last = await conv.say(text, _model if i == 0 else "Okay.")
                    turn_ms.append((time.perf_counter() - started) * 1000)
                    questions += any(m in last.text for m in _QUESTION_MARKERS)
                    reads += sum(1 for c in last.connector_calls if "send" not in c.action)
                args = (((last.pending_task or {}).get("params") or {}).get("args") or {}) if last else {}
                out.append(
                    {
                        "surface": surface,
                        "flow": label,
                        "turns": len(turns),
                        "questions": questions,
                        "approval": (last.pending_task or {}).get("status") == "awaiting_confirm" if last else False,
                        "right_recipient": args.get("to") == expected_to,
                        "reads": reads,
                        "median_turn_ms": round(statistics.median(turn_ms)),
                    }
                )
    return out


def _table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    keys = list(rows[0])
    lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    lines += ["| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows]
    return "\n".join(lines)


async def main() -> None:
    fast = await gmail_accuracy(0.0)
    slow = await gmail_accuracy(SIMULATED_READ_S)
    files = await file_accuracy()
    convs = await conversations(0.0)
    print("## Gmail lookups (no simulated latency)\n")
    print(_table(fast))
    print(f"\nAccuracy: {sum(r['ok'] for r in fast)}/{len(fast)}\n")
    print(f"## Gmail lookups ({int(SIMULATED_READ_S * 1000)} ms per simulated read)\n")
    print(_table(slow))
    print(f"\nAccuracy: {sum(r['ok'] for r in slow)}/{len(slow)}; median {statistics.median(r['ms'] for r in slow)} ms; max {max(r['ms'] for r in slow)} ms\n")
    print("## File lookups\n")
    print(_table(files))
    print(f"\nAccuracy: {sum(r['ok'] for r in files)}/{len(files)}\n")
    print("## Conversations\n")
    print(_table(convs))


if __name__ == "__main__":
    asyncio.run(main())
