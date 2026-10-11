"""Invented mailboxes and files for name-resolution tests and measurements.

Every person, address and domain here is made up (``.example``).
"""
from __future__ import annotations

from typing import Any

from tests.scenarios.conversation_harness import ORG

# The user is a Stephanie too: her own address must never be offered.
OWNER = "Stephanie Lane <stephanie.lane@gravitre.example>"
KHAN_WORK = "Stephanie Khan <stephanie.khan@acme.example>"
KHAN_HOME = "Stephanie Khan <steph.khan@gmail.example>"  # the same person's other address
WU = "Stephanie Wu <swu@globex.example>"
PARK = "Stephanie Park <spark@initech.example>"  # only ever typed into a draft
PAT = "Pat Lee <pat@acme.example>"


def mail(
    i: int,
    frm: str,
    to: str,
    labels: tuple[str, ...] = ("INBOX",),
    *,
    cc: str = "",
    subject: str = "",
    extra: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers = {"From": frm, "To": to, "Date": f"Mon, {1 + i % 28} Sep 2026 10:00:00 +0000"}
    if cc:
        headers["Cc"] = cc
    if subject:
        headers["Subject"] = subject
    headers.update(extra or {})
    return {"id": f"n{i}", "labelIds": list(labels), "headers": headers}


def noisy_mailbox() -> list[dict[str, Any]]:
    """Two different Stephanies (one with two addresses), a draft-only one,
    newsletters, no-reply senders, a mailing list, the user's own address
    and forwarded mail."""
    return [
        mail(1, KHAN_WORK, OWNER, subject="Proposal"),
        mail(2, OWNER, KHAN_WORK, ("SENT",), subject="Re: Proposal"),
        mail(3, KHAN_HOME, OWNER, subject="Weekend"),
        mail(4, WU, OWNER, cc=PAT, subject="Contract"),
        mail(5, OWNER, WU, ("SENT",), subject="Re: Contract"),
        # The user forwarded something to Wu: still mail she was sent.
        mail(6, OWNER, WU, ("SENT",), subject="Fwd: Invoice"),
        # Pat forwarded a message from a Stephanie who is only in the body.
        mail(7, PAT, OWNER, subject="Fwd: from Stephanie Moreau"),
        # Promotions newsletter with a Stephanie sender name.
        mail(
            8,
            "Stephanie at Acme Weekly <hello@acmeweekly.example>",
            OWNER,
            ("INBOX", "CATEGORY_PROMOTIONS"),
            extra={"List-Unsubscribe": "<mailto:unsub@acmeweekly.example>"},
        ),
        # A marketing sender that Gmail left in the inbox.
        mail(
            9,
            "Stephanie Rivera <stephanie@brand.example>",
            OWNER,
            extra={"List-Unsubscribe": "<https://brand.example/u>", "Precedence": "bulk"},
        ),
        # No-reply senders that use a Stephanie's name.
        mail(10, "Stephanie Khan (Docs) <comments-noreply@docs.example>", OWNER),
        mail(11, "Stephanie Wu <notifications@tracker.example>", OWNER, ("INBOX", "CATEGORY_UPDATES")),
        # A mailing list relaying a Stephanie.
        mail(
            12,
            "Stephanie Khan via Acme Team <team@lists.acme.example>",
            "Acme Team <team@lists.acme.example>",
            ("INBOX", "CATEGORY_FORUMS"),
            extra={"List-Id": "<team.lists.acme.example>"},
        ),
        # The user's own address, in a message she sent herself.
        mail(13, OWNER, OWNER, ("SENT",), subject="Note to self"),
        # Typed into a draft, never sent.
        mail(14, OWNER, PARK, ("DRAFT",), subject="Intro"),
        mail(15, PAT, OWNER, subject="Lunch"),
        mail(16, OWNER, PAT, ("SENT",), subject="Re: Lunch"),
    ]


# (query, expected status, expected addresses in order or None to skip order)
NOISY_EXPECTATIONS: list[tuple[str, str, list[str]]] = [
    ("Stephanie", "ambiguous", ["swu@globex.example", "stephanie.khan@acme.example", "steph.khan@gmail.example", "spark@initech.example"]),
    ("Stephanie Wu", "resolved", ["swu@globex.example"]),
    ("Stephanie Khan", "ambiguous", ["stephanie.khan@acme.example", "steph.khan@gmail.example"]),
    ("Stephanie Park", "ambiguous", ["spark@initech.example"]),  # draft only: confirm, never resolve
    ("Stephanie Rivera", "not_found", []),  # newsletter sender only
    ("Stephanie Moreau", "not_found", []),  # only inside a forwarded message
    ("Stephanie Lane", "not_found", []),  # the user herself
    ("Wu", "resolved", ["swu@globex.example"]),
    ("Pat", "resolved", ["pat@acme.example"]),
    ("Jordan", "not_found", []),
]


def busy_mailbox(khan_messages: int = 80) -> list[dict[str, Any]]:
    """Khan fills more pages than a lookup reads; Wu is only in the oldest mail."""
    rows = [mail(99, OWNER, PAT, ("SENT",), subject="Hello")]
    rows += [mail(100 + i, KHAN_WORK, OWNER, subject=f"Thread {i}") for i in range(khan_messages)]
    rows.append(mail(999, WU, OWNER, subject="Old contract"))
    return rows


def gmail_rows_for_two_accounts() -> list[dict[str, Any]]:
    return [
        {
            "id": "gmail-work",
            "org_id": ORG,
            "type": "gmail",
            "status": "connected",
            "environment": "production",
            "config": {"email": "stephanie.lane@gravitre.example"},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-10-10T09:00:00+00:00",
            "deleted_at": None,
        },
        {
            "id": "gmail-home",
            "org_id": ORG,
            "type": "gmail",
            "status": "connected",
            "environment": "production",
            "config": {"email": "steph.lane@home.example"},
            "created_at": "2026-02-01T00:00:00+00:00",
            "updated_at": "2026-09-01T09:00:00+00:00",
            "deleted_at": None,
        },
    ]


SHEET = "application/vnd.google-apps.spreadsheet"
DOC = "application/vnd.google-apps.document"


def budget_files() -> list[dict[str, Any]]:
    return [
        {
            "id": "f-budget-finance",
            "name": "Budget 2026",
            "mimeType": SHEET,
            "modifiedTime": "2026-10-03T12:00:00Z",
            "path": "Finance/Budget 2026",
            "webViewLink": "https://docs.example/spreadsheets/f-budget-finance",
            "source": "google_drive",
        },
        {
            "id": "f-budget-draft",
            "name": "Budget 2026",
            "mimeType": SHEET,
            "modifiedTime": "2026-09-12T12:00:00Z",
            "path": "Drafts/Budget 2026",
            "webViewLink": "https://docs.example/spreadsheets/f-budget-draft",
            "source": "google_drive",
        },
        {
            "id": "f-budget-notes",
            "name": "Budget notes",
            "mimeType": DOC,
            "modifiedTime": "2026-10-01T12:00:00Z",
            "path": "Finance/Budget notes",
            "source": "google_drive",
        },
        {
            "id": "f-q3",
            "name": "Q3 report",
            "mimeType": DOC,
            "modifiedTime": "2026-10-02T12:00:00Z",
            "content": "the budget for Q3",
            "source": "google_drive",
        },
    ]


def one_budget_file() -> list[dict[str, Any]]:
    return [f for f in budget_files() if f["id"] != "f-budget-draft"]
