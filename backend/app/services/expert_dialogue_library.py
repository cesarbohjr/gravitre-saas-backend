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
            "Our HubSpot workflow won't move contacts from MQL to SQL after a webinar — where do you look before touching the content?",
            "Start in the CRM, not the copy. Check whether lifecycle stage is being set backwards (HubSpot won't move it back without clearing it first), whether the enrollment trigger actually matches the webinar property, and whether another workflow is overwriting the stage. Once the stage moves cleanly, tie the webinar source to the contact so attribution reflects what happened.",
            "tool.hubspot.expertise — lifecycle stages, workflow enrollment triggers; marketing attribution",
        ),
        (
            "We're expanding into Germany — translate the existing blog first, or build localized landing pages?",
            "Localized landing pages first. They carry the commercial intent, and they need proper hreflang and local proof points to rank. Translate only the blog posts that support those pages. In HubSpot, set a region property on new contacts so you can see whether the German pages actually feed pipeline.",
            "SEO commercial-intent practice; international SEO (hreflang); tool.hubspot.expertise — contact properties",
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
            "Our champion on a late-stage deal just left the buyer's company — how do I treat it in the forecast?",
            "Pull it out of commit until you re-establish sponsorship. Update the existing Opportunity rather than opening a new one: mark the contact as departed, find the economic buyer or a new champion, and log a dated next step. Keep the close date honest; a deal without a sponsor usually slips, so don't discount to paper over it.",
            "tool.hubspot/salesforce — Opportunity/Deal updates, contact roles; sales pack forecast hygiene",
        ),
        (
            "Marketing wants to drop every closed-lost deal from last year into a nurture sequence — good idea?",
            "Not wholesale. Filter by loss reason first: lost on price, timing, and no-decision are worth revisiting; lost to a bad fit is not. Respect unsubscribes and opt-in status, personalize by loss reason, and let the deal owner decide when to reopen the existing Opportunity instead of opening a new one.",
            "sales pipeline practice — closed-lost re-engagement; email consent risk framing",
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
            "Can we put a customer's logo on our website because they pay us?",
            "Not by default. Check the contract for a publicity clause; many agreements prohibit logo use without written consent. If there's no clause, get a short written OK before publishing, and don't assume being a paying customer means permission.",
            "legal pack / honesty withhold — publicity rights, no assumed consent",
        ),
        (
            "A prospect's security questionnaire asks whether we're ISO 27001 certified — what do we answer?",
            "Only say yes if there's a current certificate and the scope covers the service they're buying. Otherwise describe the program honestly: which controls are in place and where the certification effort stands. Don't give a certification date nobody has committed to.",
            "legal/compliance honesty — certification claims; withhold fabrication",
        ),
        (
            "A partner's MSA has uncapped indemnity on their side only — how do you approach the redline?",
            "Make it mutual and cap it, usually at fees paid over a set period, with carve-outs limited to things like confidentiality breaches and IP infringement. Check that the liability cap and the indemnity section don't contradict each other. Don't say our playbook already approves this form unless you've checked it.",
            "legal pack — MSA indemnity/limitation of liability redlines; withhold playbook claims",
        ),
        (
            "Can we say we're GDPR ready in the MSA without a DPA?",
            "No. If you process personal data for the customer, you need a real DPA (or equivalent) and a clear roles map — controller vs processor. Don't claim GDPR ready because marketing wants a checkbox.",
            "legal/privacy — DPA vs marketing claims; withhold",
        ),
    ),
    "cybersecurity": (
        (
            "A vendor asks us to allowlist their cloud provider's entire IP range for an integration — is that fine?",
            "No. A whole provider range lets in anyone who rents a server there. Ask for their dedicated egress IPs, or use a private link or mutual TLS, keep the rule time-bound if it's for setup, and log the traffic.",
            "NIST/cyber pack — least privilege network access / zero trust framing",
        ),
        (
            "A contractor whose engagement ended last month still has admin in our identity provider — first moves?",
            "Remove the admin role and disable the account now, then rotate any shared secrets or API keys they could reach. Review the IdP audit log from their end date forward for sign-ins or grant changes. After that, require phishing-resistant MFA for the remaining admins and move admin to just-in-time elevation so offboarding gaps don't leave standing access. Don't assume SSO covered every app until you've checked.",
            "cyber pack — offboarding / credential rotation / JIT privilege",
        ),
        (
            "Vendor wants standing production access for support — yes or no?",
            "No standing production access. Use time-bound ZTNA or bastion sessions with approval, logging, and a ticket. Prefer a non-prod replica when the work allows it.",
            "cyber pack — ZTNA / time-bound / no standing prod access",
        ),
        (
            "We found an API key in a public repo — first moves?",
            "Rotate the key immediately, revoke the old credential, and check audit logs for use after exposure. Then find how it landed in git and block that path — don't leave the key live while you write a postmortem.",
            "cyber incident basics — rotate / revoke / audit",
        ),
    ),
    "hr": (
        (
            "Can we keep rejected applicants' files indefinitely in case we build a screening model later?",
            "Not as a default. Set a retention period that matches your notice to applicants and local law, and don't repurpose application data for model training without telling candidates and checking with counsel. Keep only what the retention policy allows and delete the rest on schedule.",
            "hr/privacy pack — applicant data retention and purpose limitation",
        ),
        (
            "A vendor's interview tool auto-rejects anyone under a score threshold — what do we ask before switching it on?",
            "Ask for their adverse-impact testing and whether a bias audit is required where you hire. Confirm the criteria are job-related, that candidates are told an automated tool is used, and that a person reviews before anyone is rejected. Don't turn on auto-reject just because the vendor says it's compliant.",
            "hr pack — automated employment decision tools / adverse impact / human review",
        ),
        (
            "Offer letter went out with the wrong start date — what now?",
            "Send a corrected offer letter immediately, confirm the candidate acknowledges the new terms in writing, and update the ATS/HRIS record so onboarding doesn't use the wrong date. Don't invent that verbal acknowledgment is enough if your process requires a signed letter.",
            "hr ops — offer letter correction / ATS hygiene",
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
    return ("marketing", "sales", "finance", "legal", "hr", "cybersecurity")
