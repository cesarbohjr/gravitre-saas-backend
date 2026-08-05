"""One-off probe for routing-map audit Part C / G. Do not keep as product code."""
from __future__ import annotations

from app.services.pack_common_intent_defaults import (
    try_pack_common_list_create_plan,
    try_pack_common_msp_enrich_workflow_plan,
)
from app.services.unified_turn_classical_fallback import message_requires_classical_tool_sse
from app.services.chat_orchestration_service import ChatOrchestrationService
from app.connectors.action_catalog.registry import all_catalog_action_specs

connected = ["apollo", "hubspot", "clay", "slack", "gmail"]

enrich_variants = [
    'Use Clay to enrich the existing Apollo contact list "MSP Prospects", then add those enriched contacts to the existing HubSpot static list "MSPs".',
    "enrich my apollo MSP Prospects list with Clay and sync to HubSpot MSPs",
    "Clay enrich Apollo list MSP Prospects into HubSpot list MSPs",
    "please take MSP Prospects from Apollo, enrich via Clay, put them on HubSpot MSPs",
    "run clay enrichment on the apollo msp prospects list and push to hubspot",
    "I need clay to enrich contacts then hubspot sync for msp prospects",
    "enrich contacts with clay then add to hubspot",
    "use clay enrichment for my outreach list into hubspot",
]
print("=== MSP ENRICH ===")
for m in enrich_variants:
    plan = try_pack_common_msp_enrich_workflow_plan(m, connected_integrations=connected)
    defer = message_requires_classical_tool_sse(m)
    orch = ChatOrchestrationService.is_orchestration_intent(m, {}, connected)
    print(
        ("HIT" if plan else "MISS"),
        f"defer={defer}",
        f"orch={orch}",
        "|",
        m[:75],
    )

list_variants = [
    "Create a HubSpot static list named MSPs",
    "make me a new hubspot list called MSPs",
    "add a contact list MSPs in hubspot",
    "new apollo contact list for msp outreach",
    "can you set up a list MSPs on hubspot?",
    "I want a hubspot segment named MSPs",
    "create list",
    "spin up an outreach list in apollo for MSPs",
]
print("=== LIST CREATE ===")
for m in list_variants:
    plan = try_pack_common_list_create_plan(m, connected_integrations=connected)
    print(("HIT" if plan else "MISS"), "|", m)

hs_slack = [
    "Find stale HubSpot deals and post a summary to Slack",
    "pull overdue hubspot deals then notify #sales on slack",
    "hubspot stale deals -> slack update",
    "check hubspot for deals that need attention and message the team on slack",
    "summarize cold deals from hubspot in slack",
]
print("=== HS+SLACK ORCH ===")
for m in hs_slack:
    orch = ChatOrchestrationService.is_orchestration_intent(m, {}, connected)
    defer = message_requires_classical_tool_sse(m)
    # F2: bare slack removed — defer now via LIVE needs_tool_sse (orch ⇒ True).
    print(f"orch={orch}", f"defer_pattern={defer}", f"needs_tool_sse={orch}", "|", m[:75])

# Untested connectors NL — does chat_action_mapper score anything?
from app.services.chat_action_mapper import ChatActionMapper

mapper = ChatActionMapper()
untouched = [
    ("asana", ["asana"], "create a task in Asana called Follow up with Acme"),
    ("clickup", ["clickup"], "list my open ClickUp tasks"),
    ("github", ["github"], "search GitHub issues mentioning billing"),
    ("notion", ["notion"], "create a Notion page titled Q3 plan"),
    ("airtable", ["airtable"], "find records in Airtable for Acme"),
    ("monday", ["monday"], "create a Monday.com item for onboarding"),
    ("linear", ["linear"], "create a Linear issue titled Fix login"),
    ("zendesk", ["zendesk"], "list open Zendesk tickets"),
    ("salesforce", ["salesforce"], "find Salesforce contacts named Sarah"),
    ("intercom", ["intercom"], "search Intercom conversations about refund"),
]
print("=== UNTESTED CONNECTOR MAPPER ===")
for vendor, conns, msg in untouched:
    match = mapper.match_segment(msg, connected_integrations=conns)
    if match:
        print("HIT", vendor, match.tool_name, round(match.score, 2), "|", msg[:60])
    else:
        print("MISS", vendor, "|", msg[:60])

specs = list(all_catalog_action_specs())
bad = [s.id for s in specs if len(s.id.split(".")) < 3]
print("bad_name_count", len(bad))
print("bad_sample", bad[:25])

# Descriptions: sample length + presence of when/why cues
when_why = 0
for s in specs:
    d = (s.description or "").lower()
    if any(x in d for x in ("when ", "use this", "use to", "for when", "prefer")):
        when_why += 1
print("desc_when_why_cues", when_why, "pct", round(100 * when_why / len(specs), 1))

# Enum in input_schema properties
enum_count = 0
props_total = 0
for s in specs:
    schema = s.input_schema if isinstance(getattr(s, "input_schema", None), dict) else {}
    props = schema.get("properties") if isinstance(schema, dict) else None
    if not isinstance(props, dict):
        continue
    for _k, v in props.items():
        props_total += 1
        if isinstance(v, dict) and "enum" in v:
            enum_count += 1
print("inline_schema_props", props_total, "with_enum", enum_count)

# action_parameters coverage
from app.connectors.action_catalog import action_parameters as ap

param_map = getattr(ap, "ACTION_PARAMETER_SCHEMAS", None) or getattr(
    ap, "ACTION_PARAMETERS", None
)
if param_map is None:
    # find largest dict
    candidates = [(n, getattr(ap, n)) for n in dir(ap) if not n.startswith("_")]
    dicts = [(n, v) for n, v in candidates if isinstance(v, dict) and len(v) > 50]
    dicts.sort(key=lambda x: len(x[1]), reverse=True)
    print("param_dict_candidates", [(n, len(v)) for n, v in dicts[:5]])
    param_map = dicts[0][1] if dicts else {}
print("param_map_size", len(param_map) if isinstance(param_map, dict) else 0)
ids = {s.id for s in specs}
covered = len(ids & set(param_map)) if isinstance(param_map, dict) else 0
print("specs_with_action_parameters", covered, "pct", round(100 * covered / len(specs), 1))
