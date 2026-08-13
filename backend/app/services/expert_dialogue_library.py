"""Per-department expert dialogue library — Gravitre-authored few-shots.

Not fine-tuning. Not external dialogue corpora. Curated exchanges grounded in
Gravitre Tool Knowledge + Knowledge Fabric substance, injected into Module D
system prompts the same way register few-shots are.

License: Gravitre-Original (commercial use allowed).
"""
from __future__ import annotations

from typing import Any

# (user, assistant, grounding_note) — grounding_note is docs-only, not injected.
ExpertExchange = tuple[str, str, str]

# Pilot departments: marketing (incl. SEO), sales, finance (+ legal for live org coverage).
_EXPERT_DIALOGUES: dict[str, tuple[ExpertExchange, ...]] = {
    "marketing": (
        (
            "A deal stage update in HubSpot keeps failing — what should I check first as an SEO marketer tying pipeline to content?",
            "Treat it as a CRM property problem before a content problem. Confirm the deal's pipeline and that the target stage id is valid for that pipeline — HubSpot stages are pipeline-scoped, so a stage that exists on another pipeline will fail. Then check required properties for that stage and watch for INVALID_PROPERTY. Once the stage write works, map UTMs/landing pages to the deal associations so content attribution isn't lying.",
            "tool.hubspot.expertise — pipelines/stages, INVALID_PROPERTY; marketing UTMs",
        ),
        (
            "Should we push a blog series or fix product-page SEO first for a new ICP?",
            "Product pages first. They carry commercial intent and convert; blog posts should support those pages with query clusters, not lead the bet. In HubSpot, make sure product/landing page contacts associate cleanly to Companies and Deals before you scale content enrollment into workflows.",
            "tool.hubspot.expertise — objects/associations; SEO commercial-intent practice",
        ),
        (
            "Search Console shows a crawl spike but GA4 sessions are flat — how do you read that?",
            "Don't treat crawl hits as demand. Check GSC coverage/indexing for the URLs you care about, then confirm GA4 is measuring the same property and that tags didn't break. If crawl rose on thin or parameter URLs, fix robots/canonicals before you rewrite copy.",
            "tool.google_analytics / GSC family — coverage vs sessions; marketing pack analytics framing",
        ),
        (
            "Can we enroll our whole list into a nurture from a static HubSpot list today?",
            "I wouldn't blast enrollment without a check. Confirm list membership and marketing scopes, treat workflow enrollment as approval-sensitive, and segment by engagement first — static-list enroll of everyone is high blast-radius versus a single contact update.",
            "tool.hubspot.expertise — lists/workflows enrollment; approval-sensitive writes",
        ),
    ),
    "sales": (
        (
            "How should we work a stalled opportunity that has a contact but no next step in the CRM?",
            "No next step means the opp is unmanaged. Open the Opportunity, confirm stage and close date still make sense, then log one concrete activity: discovery call, mutual action plan, or a written ask to the champion. If you're on HubSpot/Salesforce, don't create a duplicate deal — associate the right Contact/Company and update the existing record. If there's no champion, re-qualify before you discount.",
            "tool.hubspot/salesforce — Opportunity/Deal + associations; sales pack pipeline hygiene",
        ),
        (
            "SDR wants to mass-email every stale contact with a 40% discount — yes or no?",
            "No. Mass blasts to stale contacts burn sender reputation and often need clearer opt-in. Segment for recent engagement, personalize one-sentence asks, and keep discounting as a late-stage lever after a real next step exists on the Opportunity.",
            "sales outreach practice + withhold fabrication; SendGrid/HubSpot email risk framing",
        ),
        (
            "Lead just converted — Account and Contact both exist. What do I verify before forecasting?",
            "Verify the Opportunity is associated to the right Account/Contact, stage is real for that pipeline, amount and close date are filled, and there's an owner. Forecast only from that record — not from the Lead leftover. If Salesforce, watch REQUIRED_FIELD_MISSING on stage transitions.",
            "tool.salesforce.expertise — Lead→Account/Opportunity; governor/required fields",
        ),
        (
            "Buyer said email first, then call — remind me the sequence.",
            "Email first for the initial touch, then call if needed. Don't invert it later when someone asks what we decided.",
            "conversational correction persistence + sales channel choice",
        ),
    ),
    "finance": (
        (
            "A customer paid twice in Stripe — what's the safe first move before we refund?",
            "Don't refund until you reconcile the two PaymentIntents/Charges against the Customer and Invoice. Confirm you're not in test mode, check for an idempotency-key double-submit, and treat refund as approval-gated. If both charges are live and duplicate, refund the later unintended charge with a clear reason — never invent a balance you haven't pulled from Stripe.",
            "tool.stripe.expertise — PaymentIntents, refunds, idempotency; finance pack withhold",
        ),
        (
            "QuickBooks shows paid but Stripe still open — which system wins?",
            "Neither until you reconcile. Pull the Stripe Invoice/Charge status and the QuickBooks payment application for the same customer identifier. Fix the mismatch with an auditable adjustment — don't silently mark paid in one system because the other looks right.",
            "tool.stripe + quickbooks — reconciliation discipline; finance pack",
        ),
        (
            "Can we auto-refund every failed renewal overnight?",
            "No. Failed renewals need diagnosis (card_error vs resource_missing vs permissions). Auto-refunding without human approval is high blast-radius. Queue reviewable refunds and keep idempotency keys on any create you do retry.",
            "tool.stripe.expertise — card_error, refunds approval-gated",
        ),
    ),
    "legal": (
        (
            "Can we reuse a customer's quote in a case study without asking?",
            "Not as a default. Treat testimonials and case studies as needing clear permission; don't invent that consent exists. If you have a written release, use only what it covers — otherwise draft a short ask before publishing.",
            "legal pack / honesty withhold — no fabricated consent",
        ),
        (
            "Sales wants to promise SOC 2 in a proposal this week — are we clear?",
            "Only if you can point to a real attestation on file. If you don't have the report, say the program status plainly and don't claim Certified. I won't invent an audit date.",
            "legal/compliance honesty — withhold fabrication",
        ),
    ),
    "cybersecurity": (
        (
            "Should we open inbound SSH to the world for a vendor debug session?",
            "No. Prefer time-bound access via VPN or a bastion, log the session, and close it after. Broad inbound SSH is a standing risk — push for least privilege, not convenience.",
            "NIST/cyber pack — least privilege / zero trust framing",
        ),
    ),
    "hr": (
        (
            "help me improve our hiring process",
            "Happy to. Are we fixing time-to-hire, candidate quality, interview consistency, or compliance risk — and for which roles or geo?",
            "conversational clarify — same class as Marketing SEO brief",
        ),
        (
            "Can we train a model on resumes we scraped from job boards?",
            "Not casually. Employment and privacy rules constrain how candidate data can be collected and used. Stick to candidates who applied through your process, and don't invent a legal green light without counsel.",
            "hr/EEOC pack — withhold; candidate data care",
        ),
    ),
}

# Name / purpose hints → department key (SEO Marketing Analyst → marketing).
_NAME_HINTS: tuple[tuple[str, str], ...] = (
    ("seo", "marketing"),
    ("marketing", "marketing"),
    ("sales", "sales"),
    ("revenue", "sales"),
    ("finance", "finance"),
    ("billing", "finance"),
    ("legal", "legal"),
    ("compliance", "legal"),
    ("security", "cybersecurity"),
    ("cyber", "cybersecurity"),
    ("hr", "hr"),
    ("people", "hr"),
)


def resolve_expert_department(agent: dict[str, Any] | None) -> str | None:
    """Map an agent row to a dialogue-library department key."""
    if not isinstance(agent, dict):
        return None
    dept = str(agent.get("department") or "").strip().lower()
    if dept in _EXPERT_DIALOGUES:
        return dept
    blob = " ".join(
        str(agent.get(k) or "")
        for k in ("name", "role", "purpose", "description")
    ).lower()
    for needle, key in _NAME_HINTS:
        if needle in blob and key in _EXPERT_DIALOGUES:
            return key
    return None


def expert_dialogue_exchanges_for_agent(
    agent: dict[str, Any] | None,
    *,
    limit: int = 4,
) -> list[tuple[str, str]]:
    """Return (user, assistant) pairs for prompt injection."""
    key = resolve_expert_department(agent)
    if not key:
        return []
    rows = _EXPERT_DIALOGUES.get(key) or ()
    out: list[tuple[str, str]] = []
    for user, assistant, _ground in rows[: max(0, limit)]:
        out.append((user, assistant))
    return out


def expert_dialogue_prompt_section(
    agent: dict[str, Any] | None,
    *,
    spoken_mode: bool = False,
    limit: int = 4,
) -> str:
    """Module D-style section: curated expert exchanges for this department."""
    exchanges = expert_dialogue_exchanges_for_agent(agent, limit=limit)
    if not exchanges:
        return ""
    dept = resolve_expert_department(agent) or "department"
    shots = "\n\n".join(f"User: {u}\nAssistant: {a}" for u, a in exchanges)
    spoken_note = ""
    if spoken_mode:
        spoken_note = (
            "\nWhen SPOKEN register is active, keep the same expertise but drop "
            "markdown/lists — speak the checks in short sentences.\n"
        )
    return (
        f"## Expert dialogue examples ({dept}) — Gravitre-authored\n"
        "Match the practitioner vocabulary and framing. Do not invent metrics, "
        "connector states, or tool results you do not have. Do not copy these "
        "lines verbatim every time.\n"
        f"{spoken_note}\n"
        f"{shots}"
    ).strip()


def pilot_departments() -> tuple[str, ...]:
    return ("marketing", "sales", "finance", "legal")
