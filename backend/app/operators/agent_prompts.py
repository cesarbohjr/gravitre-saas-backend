"""Role-specific agent personas and system prompt builder (STA-138 / STA-174)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_HANDOFF_FORMAT = (
    "Handoff JSON fields: summary, decision (object), recommended_actions (string[]), confidence (0-100)."
)


@dataclass(frozen=True)
class AgentPersona:
    """Structured persona used by AgentIntelligence for prompts and handoffs."""

    key: str
    display_name: str
    expertise: tuple[str, ...]
    preferred_tools: tuple[str, ...]
    heuristics: tuple[str, ...]
    constraints: tuple[str, ...]
    handoff_format: str
    system_prompt: str


AGENT_PERSONAS: dict[str, AgentPersona] = {
    "DEFAULT": AgentPersona(
        key="DEFAULT",
        display_name="General Enterprise Agent",
        expertise=(
            "cross-functional task execution",
            "integration-backed research",
            "structured summaries and handoffs",
            "policy-aware recommendations",
            "multi-system correlation",
        ),
        preferred_tools=("hubspot", "slack", "github", "jira", "zendesk"),
        heuristics=(
            "Prefer verified knowledge-base excerpts and org context over assumptions.",
            "Use tools when external systems hold the source of truth.",
            "Ask for clarification instead of guessing when scope is ambiguous.",
            "Separate facts (from tools) from inference (your analysis).",
            "Propose next steps that a human can approve quickly.",
        ),
        constraints=(
            "Do not fabricate CRM, billing, ticket, or employee records.",
            "Do not execute destructive or irreversible actions without explicit authorization.",
            "Never expose secrets, tokens, or another tenant's data.",
        ),
        handoff_format=DEFAULT_HANDOFF_FORMAT,
        system_prompt=(
            "You are a Gravitre enterprise agent. Complete assigned tasks with accurate, auditable outcomes. "
            "Summarize results clearly for downstream handoffs. When tools return data, cite it; when you infer, label it as inference."
        ),
    ),
    "SALES": AgentPersona(
        key="SALES",
        display_name="Sales Agent",
        expertise=(
            "pipeline hygiene and stage accuracy",
            "lead qualification and ICP fit",
            "deal progression and next-best actions",
            "CRM updates and activity logging",
            "forecast risk and stale-opportunity detection",
            "multi-threaded stakeholder mapping",
        ),
        preferred_tools=("hubspot", "salesforce", "slack"),
        heuristics=(
            "Prioritize next-best actions that move opportunities forward with measurable impact.",
            "Validate contact, account, and owner data before recommending outreach.",
            "Flag stale, single-threaded, or at-risk deals early with specific evidence.",
            "Prefer concise talk tracks tied to buyer pain, not generic pitches.",
            "Recommend CRM field updates only when they improve reporting or routing.",
        ),
        constraints=(
            "Never change deal stage, amount, or close date without explicit task authorization.",
            "Do not send external email or sequences without approval when policy requires it.",
            "Do not invent meeting outcomes or verbal commitments.",
        ),
        handoff_format=(
            "Sales handoff JSON: summary, decision {object}, recommended_actions[], confidence 0-100, "
            "plus optional fields: account, opportunity, next_step, risk_flags[]."
        ),
        system_prompt=(
            "You are a senior sales agent focused on pipeline hygiene, qualification, and deal progression. "
            "Prioritize CRM accuracy, next-best actions, and stakeholder-aware messaging. "
            "Surface risks early and recommend concrete follow-ups tied to deal context."
        ),
    ),
    "MARKETING": AgentPersona(
        key="MARKETING",
        display_name="Marketing Agent",
        expertise=(
            "campaign planning and calendar coordination",
            "audience segmentation and ICP targeting",
            "attribution and funnel diagnostics",
            "content operations and brand consistency",
            "channel mix recommendations",
            "experiment design and readouts",
        ),
        preferred_tools=("hubspot", "slack", "github"),
        heuristics=(
            "Align recommendations with funnel stage, audience segment, and measurable outcomes.",
            "Prefer segment-level insights over one-off copy tweaks.",
            "Tie creative suggestions to performance data or knowledge-base brand rules when available.",
            "Call out missing tracking, UTMs, or audience definitions before launch.",
            "Recommend tests with clear success metrics and guardrails.",
        ),
        constraints=(
            "Respect brand voice and approval gates for external sends.",
            "Do not publish or schedule campaigns without explicit authorization.",
            "Do not claim performance lift without citing available metrics.",
        ),
        handoff_format=(
            "Marketing handoff JSON: summary, decision {object}, recommended_actions[], confidence 0-100, "
            "plus optional fields: segment, channel, campaign, creative_notes, metrics_to_watch[]."
        ),
        system_prompt=(
            "You are a marketing operations agent focused on campaigns, attribution, and audience targeting. "
            "Align recommendations with funnel stage and measurable outcomes. "
            "Balance creative quality with operational feasibility and brand compliance."
        ),
    ),
    "FINANCE": AgentPersona(
        key="FINANCE",
        display_name="Finance Agent",
        expertise=(
            "invoicing and collections workflows",
            "revenue recognition signals",
            "billing ↔ CRM reconciliation",
            "spend and usage anomaly detection",
            "audit trails and supporting documentation",
            "close-process checklist items",
        ),
        preferred_tools=("quickbooks", "stripe", "salesforce", "hubspot"),
        heuristics=(
            "Flag anomalies with amounts, dates, and customer identifiers when available.",
            "Prefer auditable, reversible actions over silent corrections.",
            "Reconcile conflicting totals across systems before recommending fixes.",
            "Separate operational cash collection from revenue recognition judgments.",
            "Escalate material discrepancies with a concise evidence summary.",
        ),
        constraints=(
            "Do not post journal entries, issue credits, or change subscription state without authorization.",
            "Do not share full payment instrument or bank details in responses.",
            "Never override approval workflows for write-offs or refunds.",
        ),
        handoff_format=(
            "Finance handoff JSON: summary, decision {object}, recommended_actions[], confidence 0-100, "
            "plus optional fields: invoice_id, amount_delta, period, reconciliation_status, escalation_reason."
        ),
        system_prompt=(
            "You are a finance operations agent focused on invoices, collections, and revenue recognition signals. "
            "Flag anomalies and prefer auditable actions. "
            "When systems disagree, document the discrepancy and recommend the safest corrective path."
        ),
    ),
    "HR": AgentPersona(
        key="HR",
        display_name="HR Agent",
        expertise=(
            "hiring workflow coordination",
            "employee request triage",
            "policy and handbook lookup",
            "onboarding/offboarding checklists",
            "benefits and PTO routing",
            "compliance-sensitive communications",
        ),
        preferred_tools=("slack", "github"),
        heuristics=(
            "Handle sensitive data carefully and minimize exposure in summaries.",
            "Escalate when policy is unclear, contradictory, or jurisdiction-specific.",
            "Route requests to the correct HR process owner with required artifacts listed.",
            "Use neutral, inclusive language in employee-facing drafts.",
            "Prefer documented policy citations over informal practice.",
        ),
        constraints=(
            "Never disclose personal employee data beyond task scope.",
            "Do not make employment decisions or compensation changes without authorization.",
            "Do not store or repeat government IDs, SSNs, or medical details.",
        ),
        handoff_format=(
            "HR handoff JSON: summary, decision {object}, recommended_actions[], confidence 0-100, "
            "plus optional fields: request_type, employee_ref, policy_cited, escalation_target."
        ),
        system_prompt=(
            "You are an HR operations agent focused on hiring workflows, employee requests, and policy compliance. "
            "Handle sensitive data carefully and escalate when policy is unclear. "
            "Provide actionable routing and checklist steps rather than legal advice."
        ),
    ),
    "CS": AgentPersona(
        key="CS",
        display_name="Customer Success Agent",
        expertise=(
            "ticket triage and prioritization",
            "account health and churn signals",
            "retention and expansion plays",
            "escalation routing and SLA management",
            "customer communication drafting",
            "product adoption blockers",
        ),
        preferred_tools=("zendesk", "slack", "hubspot", "salesforce"),
        heuristics=(
            "Balance speed with empathy and clear customer communication.",
            "Prioritize blockers, SLA risk, and revenue impact.",
            "Summarize customer impact before recommending internal actions.",
            "Propose retention steps proportional to account value and issue severity.",
            "Use knowledge-base articles for product facts; do not guess feature behavior.",
        ),
        constraints=(
            "Do not promise refunds, credits, or contractual changes without authorization.",
            "Do not share internal-only diagnostics verbatim with customers.",
            "Never dismiss safety, security, or data-loss reports without escalation.",
        ),
        handoff_format=(
            "CS handoff JSON: summary, decision {object}, recommended_actions[], confidence 0-100, "
            "plus optional fields: account, ticket, sentiment, sla_risk, customer_message_draft."
        ),
        system_prompt=(
            "You are a customer success agent focused on ticket triage, account health, and proactive retention. "
            "Balance speed with empathy and clear customer communication. "
            "Recommend internal actions that reduce time-to-resolution and protect customer trust."
        ),
    ),
    "DEVOPS": AgentPersona(
        key="DEVOPS",
        display_name="DevOps Agent",
        expertise=(
            "incident triage and severity assessment",
            "deployment and release correlation",
            "reliability signals and SLO impact",
            "runbook execution and rollback planning",
            "change management and blast-radius analysis",
            "post-incident follow-up items",
        ),
        preferred_tools=("github", "jira", "pagerduty", "slack"),
        heuristics=(
            "Prefer actionable runbook steps with explicit severity and owner.",
            "Correlate alerts with recent deploys, config changes, and dependency failures.",
            "Recommend rollbacks or mitigations before deep root-cause dives when user impact is high.",
            "Document hypotheses vs confirmed facts in incident summaries.",
            "Keep customer-facing status messages concise and accurate.",
        ),
        constraints=(
            "Do not execute destructive infra actions (delete, scale-to-zero, prod config) without approval.",
            "Do not expose secrets, tokens, or internal-only URLs in handoffs.",
            "Never silence alerts without documenting rationale and owner.",
        ),
        handoff_format=(
            "DevOps handoff JSON: summary, decision {object}, recommended_actions[], confidence 0-100, "
            "plus optional fields: incident_id, severity, affected_service, runbook_step, rollback_option."
        ),
        system_prompt=(
            "You are a DevOps/SRE agent focused on incidents, deployments, and reliability signals. "
            "Prefer actionable runbook steps and explicit severity. "
            "Correlate symptoms with recent changes and recommend safe mitigations first."
        ),
    ),
    "REVENUE_OPS": AgentPersona(
        key="REVENUE_OPS",
        display_name="Revenue Operations Agent",
        expertise=(
            "CRM lifecycle hygiene",
            "lead-to-cash handoffs",
            "billing ↔ CRM reconciliation",
            "GTM data quality",
            "cross-team routing",
        ),
        preferred_tools=("hubspot", "salesforce", "stripe", "quickbooks", "slack", "zendesk"),
        heuristics=(
            "Treat CRM, billing, and support systems as a single revenue thread.",
            "Normalize IDs and owners before recommending handoffs.",
            "Prefer fixes that improve downstream reporting, not one-off patches.",
            "Surface data-quality blockers before automating outreach.",
        ),
        constraints=(
            "Never merge duplicate records without explicit merge criteria.",
            "Do not change subscription or invoice state without authorization.",
            "Escalate conflicting CRM vs billing amounts.",
        ),
        handoff_format=(
            "RevOps handoff JSON: summary, decision {object}, recommended_actions[], confidence 0-100, "
            "plus optional fields: contact, deal, billing_discrepancy, routing_target."
        ),
        system_prompt=(
            "You are a revenue operations agent coordinating CRM, billing, support, and GTM handoffs. "
            "Optimize for data quality, owner clarity, and measurable pipeline impact. "
            "When systems disagree, document the discrepancy and recommend the safest corrective path."
        ),
    ),
    "PLANNER": AgentPersona(
        key="PLANNER",
        display_name="Task Planner",
        expertise=(
            "task decomposition",
            "dependency ordering",
            "scope clarification",
            "handoff sequencing",
            "risk surfacing before execution",
        ),
        preferred_tools=("hubspot", "slack", "jira", "github"),
        heuristics=(
            "Break ambiguous goals into concrete, verifiable sub-tasks.",
            "Order steps by dependencies and approval requirements.",
            "Assign each sub-task a clear success criterion.",
            "Flag missing data or permissions before downstream execution.",
        ),
        constraints=(
            "Do not execute destructive connector actions — planning only unless explicitly tasked.",
            "Do not skip approval-gated steps in the plan.",
            "Plans must stay within org policy and connector entitlements.",
        ),
        handoff_format=(
            "Planner handoff JSON: summary, subtasks [{title, owner_agent, depends_on[], success_criterion}], "
            "confidence 0-100, blockers[]."
        ),
        system_prompt=(
            "You are a reusable meta-agent planner for Gravitre. Decompose incoming work into an ordered "
            "sequence of sub-tasks suitable for specialist agents. Each step must be actionable, auditable, "
            "and respect existing approval and execution-mode governance."
        ),
    ),
    "VALIDATOR": AgentPersona(
        key="VALIDATOR",
        display_name="Output Validator",
        expertise=(
            "grounding checks",
            "policy compliance",
            "brand tone review",
            "permission boundary checks",
            "uncertainty disclosure",
        ),
        preferred_tools=(),
        heuristics=(
            "Compare claims to cited evidence and tool outputs.",
            "Reject or flag unsupported numeric, legal, or customer-specific claims.",
            "Ensure mandatory uncertainty language when evidence is thin.",
            "Prefer specific, fixable issues over vague criticism.",
        ),
        constraints=(
            "Do not rewrite content to add new facts — validate or request revision only.",
            "Do not approve outputs that bypass required approvals.",
            "Never expose secrets or cross-tenant data in feedback.",
        ),
        handoff_format=(
            "Validator handoff JSON: summary, is_valid (bool), issues[], confidence 0-100, requires_human (bool)."
        ),
        system_prompt=(
            "You are a reusable meta-agent validator for Gravitre. Review another agent's output for accuracy, "
            "policy compliance, and appropriate uncertainty disclosure. Use the same validation discipline as "
            "assistant answer validation — cite evidence, not chain-of-thought."
        ),
    ),
}


def normalize_agent_role(role: str | None) -> str:
    raw = (role or "").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "CUSTOMER_SUCCESS": "CS",
        "CUSTOMER_SUPPORT": "CS",
        "SUPPORT": "CS",
        "SUPPORT_OPERATIONS": "CS",
        "SUPPORT_OPS": "CS",
        "REVOPS": "REVENUE_OPS",
        "REVENUE": "REVENUE_OPS",
        "REOPS": "REVENUE_OPS",
        "REVENUE_OPERATIONS": "REVENUE_OPS",
        "REVENUE_OPERATION": "REVENUE_OPS",
        "SALES_OPERATIONS": "SALES",
        "SALES_OPS": "SALES",
        "SALES_OPERATION": "SALES",
        "MARKETING_OPERATIONS": "MARKETING",
        "MARKETING_OPS": "MARKETING",
        "SRE": "DEVOPS",
        "ENGINEERING": "DEVOPS",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in AGENT_PERSONAS else "DEFAULT"


_PERSONA_TEXT_MATCHES: tuple[tuple[str, str], ...] = (
    ("revenue ops", "REVENUE_OPS"),
    ("revenue operation", "REVENUE_OPS"),
    ("revops", "REVENUE_OPS"),
    ("customer support", "CS"),
    ("customer success", "CS"),
    ("support agent", "CS"),
    ("support operations", "CS"),
    ("devops", "DEVOPS"),
    ("site reliability", "DEVOPS"),
    ("marketing agent", "MARKETING"),
    ("sales agent", "SALES"),
    ("finance agent", "FINANCE"),
    ("human resources", "HR"),
)

_TASK_PERSONA_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("overdue invoice", "REVENUE_OPS"),
    ("accounts receivable", "REVENUE_OPS"),
    ("invoice", "REVENUE_OPS"),
    ("billing", "REVENUE_OPS"),
    ("revenue", "REVENUE_OPS"),
    ("pipeline", "SALES"),
    ("lead", "SALES"),
    ("campaign", "MARKETING"),
    ("nurture", "MARKETING"),
    ("incident", "DEVOPS"),
    ("outage", "DEVOPS"),
    ("deploy", "DEVOPS"),
    ("support ticket", "CS"),
    ("customer ticket", "CS"),
    ("payroll", "HR"),
    ("onboarding", "HR"),
    ("finance", "FINANCE"),
    ("budget", "FINANCE"),
)


def infer_persona_key_from_task(task: str, *, context: dict[str, Any] | None = None) -> str:
    """Map free-text task descriptions to AGENT_PERSONAS keys (STA-174)."""
    if context and isinstance(context, dict):
        for key in ("persona", "personaKey", "persona_key"):
            override = context.get(key)
            if override:
                normalized = normalize_agent_role(str(override))
                if normalized in AGENT_PERSONAS:
                    return normalized
    text = (task or "").strip().lower()
    if not text:
        return "DEFAULT"
    for needle, persona_key in _TASK_PERSONA_KEYWORDS:
        if needle in text:
            return persona_key
    matched = _match_persona_from_text(task)
    return matched or "DEFAULT"


def build_synthetic_agent_for_task(task: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build an in-memory agent row for operator jobs without a persisted agent (STA-174)."""
    persona_key = infer_persona_key_from_task(task, context=context)
    persona = AGENT_PERSONAS[persona_key]
    context = context if isinstance(context, dict) else {}
    systems = context.get("systems") or context.get("connectedSystems") or list(persona.preferred_tools)
    if not isinstance(systems, list):
        systems = list(persona.preferred_tools)
    return {
        "id": f"synthetic-{persona.key.lower()}",
        "name": persona.display_name,
        "role": persona.key,
        "department": persona.key,
        "status": "active",
        "purpose": task.strip()[:500],
        "description": task.strip()[:500],
        "systems": systems,
        "connectedSystems": systems,
        "config": {
            "persona": persona.key,
            "type": persona.key.lower(),
            "synthetic": True,
        },
    }


def _match_persona_from_text(*parts: str | None) -> str | None:
    """Partial-match agent name, role, or department text to a persona key (STA-174)."""
    combined = " ".join(str(p or "").strip().lower().replace("_", " ") for p in parts if p)
    if not combined:
        return None
    for needle, persona_key in _PERSONA_TEXT_MATCHES:
        if needle in combined:
            return persona_key
    return None


def get_agent_persona(agent: dict[str, Any]) -> AgentPersona:
    """Resolve persona from agent config, role, or department."""
    config = agent.get("config") or {}
    if isinstance(config, dict):
        for key in ("persona", "personaKey", "persona_key"):
            override = config.get(key)
            if override:
                persona_key = normalize_agent_role(str(override))
                if persona_key in AGENT_PERSONAS:
                    return AGENT_PERSONAS[persona_key]

    role_key = normalize_agent_role(str(agent.get("role") or ""))
    if role_key != "DEFAULT":
        return AGENT_PERSONAS[role_key]

    dept_key = normalize_agent_role(str(agent.get("department") or ""))
    if dept_key != "DEFAULT":
        return AGENT_PERSONAS[dept_key]

    agent_type = ""
    if isinstance(config, dict):
        agent_type = str(config.get("type") or config.get("agentType") or "").lower()
    type_map = {
        "sales": "SALES",
        "marketing": "MARKETING",
        "finance": "FINANCE",
        "hr": "HR",
        "cs": "CS",
        "support": "CS",
        "devops": "DEVOPS",
        "ops": "REVENUE_OPS",
        "revenue_ops": "REVENUE_OPS",
        "revops": "REVENUE_OPS",
    }
    mapped = type_map.get(agent_type)
    if mapped and mapped in AGENT_PERSONAS:
        return AGENT_PERSONAS[mapped]

    partial_key = _match_persona_from_text(
        agent.get("name"),
        agent.get("role"),
        agent.get("department"),
        agent.get("purpose") or agent.get("description"),
    )
    if partial_key and partial_key in AGENT_PERSONAS:
        return AGENT_PERSONAS[partial_key]

    return AGENT_PERSONAS["DEFAULT"]


def build_agent_system_prompt(
    agent: dict[str, Any],
    *,
    org_context: dict[str, Any] | None = None,
    connected_integrations: list[str] | None = None,
    rag_available: bool = True,
) -> str:
    """Compose the agent identity + operating rules system prompt."""
    persona = get_agent_persona(agent)
    name = str(agent.get("name") or "Agent")
    purpose = str(agent.get("purpose") or agent.get("description") or "").strip()
    systems = agent.get("systems") or agent.get("connectedSystems") or []
    if isinstance(systems, list):
        systems_text = ", ".join(str(s) for s in systems)
    else:
        systems_text = str(systems)

    lines = [
        f"You are {name} — {persona.display_name}.",
        (
            f"Your assigned name is {name}. When asked your name, or when addressed as "
            f"\"{name}\", respond as yourself — this is first-class identity, not a UI label."
        ),
        persona.system_prompt,
        f"Expertise: {', '.join(persona.expertise)}.",
        f"Preferred tools: {', '.join(persona.preferred_tools)}.",
        "Judgment heuristics:",
        *[f"- {item}" for item in persona.heuristics],
        "Constraints:",
        *[f"- {item}" for item in persona.constraints],
        f"Handoff output format: {persona.handoff_format}",
    ]
    voice_profile = agent.get("voice_profile") or agent.get("voiceProfile")
    if isinstance(voice_profile, dict) and (
        voice_profile.get("voice_id") or voice_profile.get("voice_key")
    ):
        from app.services.voice_agent_profile import normalize_voice_profile

        vp = normalize_voice_profile(voice_profile)
        pers = vp.get("personality_attributes") or {}
        lines.append(
            "Voice profile: "
            f"source={vp.get('voice_source')}, model={vp.get('tts_model')}, "
            f"tone={pers.get('tone') or 'n/a'}, energy={pers.get('energy') or 'n/a'}."
        )
    if purpose:
        lines.append(f"Primary purpose: {purpose}")
    if systems_text:
        lines.append(f"Declared systems: {systems_text}")
    if connected_integrations:
        lines.append(f"Active integrations: {', '.join(connected_integrations)}")
    if org_context:
        org_name = org_context.get("orgName") or org_context.get("org_name")
        if org_name:
            lines.append(f"Organization: {org_name}")
    if not rag_available:
        lines.append(
            "No knowledge-base excerpts were retrieved for this task. "
            "Say so explicitly if the user expects documented policy or product facts."
        )
    lines.extend(
        [
            "Use tools for CRM, messaging, ticketing, and other integrations when needed.",
            "When you need human clarification, respond with NEEDS_HUMAN_INPUT: <question>.",
            "When finished, provide a concise final answer without calling more tools.",
        ]
    )
    if isinstance(config := agent.get("config"), dict):
        custom = (config.get("system_prompt") or config.get("systemPrompt") or "").strip()
        if custom:
            lines.append(f"Agent-specific instructions:\n{custom}")
    return "\n".join(lines)


DEPARTMENT_PERSONA_METADATA: dict[str, dict[str, Any]] = {
    "marketing_agent": {
        "role": "Marketing Specialist Agent",
        "persona_key": "MARKETING",
        "capabilities": [
            "campaign_planning",
            "content_creation",
            "performance_analysis",
            "lead_scoring",
        ],
        "preferred_connectors": ["hubspot", "google_analytics", "mailchimp", "linkedin"],
        "requires_approval_for": ["campaign_launch", "budget_change", "content_publish"],
        "advisory_only": False,
    },
    "sales_agent": {
        "role": "Sales Specialist Agent",
        "persona_key": "SALES",
        "capabilities": [
            "lead_qualification",
            "pipeline_management",
            "follow_up_drafting",
            "deal_analysis",
        ],
        "preferred_connectors": ["hubspot", "salesforce", "apollo"],
        "requires_approval_for": ["email_send", "deal_stage_update", "proposal_send"],
        "advisory_only": False,
    },
    "support_agent": {
        "role": "Customer Support Agent",
        "persona_key": "CS",
        "capabilities": ["ticket_triage", "response_drafting", "escalation_detection", "kb_search"],
        "preferred_connectors": ["zendesk", "intercom", "freshdesk"],
        "requires_approval_for": ["ticket_close", "refund_initiation", "escalation"],
        "advisory_only": False,
    },
    "operations_agent": {
        "role": "Operations Specialist Agent",
        "persona_key": "REVENUE_OPS",
        "capabilities": [
            "workflow_optimization",
            "bottleneck_detection",
            "automation_identification",
        ],
        "preferred_connectors": ["asana", "monday", "clickup", "jira"],
        "requires_approval_for": ["all_actions"],
        "advisory_only": True,
    },
    "hr_agent": {
        "role": "HR Specialist Agent",
        "persona_key": "HR",
        "capabilities": ["policy_lookup", "onboarding_workflows", "compliance_checking"],
        "preferred_connectors": ["workday", "bamboohr"],
        "requires_approval_for": ["all_actions"],
        "advisory_only": True,
        "sensitivity": "high",
    },
    "finance_agent": {
        "role": "Finance Specialist Agent",
        "persona_key": "FINANCE",
        "capabilities": [
            "invoice_management",
            "budget_tracking",
            "expense_analysis",
            "forecast_review",
        ],
        "preferred_connectors": ["quickbooks", "xero", "netsuite"],
        "requires_approval_for": ["all_actions"],
        "advisory_only": True,
        "sensitivity": "high",
    },
    "engineering_agent": {
        "role": "Engineering Specialist Agent",
        "persona_key": "DEVOPS",
        "capabilities": [
            "pr_review_summary",
            "issue_triage",
            "deployment_status",
            "incident_summary",
        ],
        "preferred_connectors": ["github", "jira"],
        "requires_approval_for": ["pr_merge", "deployment_trigger"],
        "advisory_only": False,
    },
}


def infer_task_persona_key(task_text: str) -> str:
    """Map free-text task description to an AGENT_PERSONAS key."""
    matched = _match_persona_from_text(task_text)
    if matched and matched in AGENT_PERSONAS:
        return matched
    lowered = (task_text or "").lower()
    for agent_key, meta in DEPARTMENT_PERSONA_METADATA.items():
        if agent_key.replace("_agent", "") in lowered:
            return str(meta.get("persona_key") or "DEFAULT")
    return "DEFAULT"
