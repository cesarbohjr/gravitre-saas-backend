"""Unique People/IT and Executive definitions from #267 on the canonical registry.

Blueprints have no measured results or production certification. No separate runtime.
"""
from typing import Any

PACK_SPECS = {'people-it-operations-3': {'title': 'People & IT Operations 3.0',
                            'department': 'People & IT Operations',
                            'skill_package': 'people-it-operations-skills',
                            'problem': 'Employee lifecycle and IT service work '
                                       'become fragmented across HR records, '
                                       'onboarding, service requests, access '
                                       'checks, and device/support queues.',
                            'target': 'Improve employee onboarding and service '
                                      'readiness while reducing incomplete '
                                      'requests, access gaps, and manual '
                                      'coordination.',
                            'connectors': ['bamboohr', 'freshservice'],
                            'optional': ['rippling',
                                         'hibob',
                                         'okta',
                                         'jumpcloud',
                                         'microsoft_intune',
                                         'jamf_pro'],
                            'profiles': {'bamboohr': ['bamboohr.employees.list',
                                                      'bamboohr.employees.get',
                                                      'bamboohr.timeoff.requests.list'],
                                         'freshservice': ['freshservice.tickets.list',
                                                          'freshservice.tickets.get']},
                            'agents': [('employee-operations-agent',
                                        'Employee Operations Agent'),
                                       ('it-service-readiness-agent',
                                        'IT Service Readiness Agent')],
                            'kpis': [('onboarding_readiness',
                                      'Onboarding readiness',
                                      'percent',
                                      'increase'),
                                     ('offboarding_readiness',
                                      'Offboarding readiness',
                                      'percent',
                                      'increase'),
                                     ('policy_request_age',
                                      'Policy request age',
                                      'hours',
                                      'decrease'),
                                     ('employee_request_age',
                                      'Employee request age',
                                      'hours',
                                      'decrease'),
                                     ('access_review_gap',
                                      'Access review gap',
                                      'percent',
                                      'decrease'),
                                     ('device_service_risk',
                                      'Device/service risk',
                                      'count',
                                      'decrease'),
                                     ('license_review_gap',
                                      'License review gap',
                                      'percent',
                                      'decrease')],
                            'plays': [('onboarding-readiness-review',
                                       'Onboarding Readiness Review',
                                       'Check employee and service evidence '
                                       'for onboarding blockers before start '
                                       'date.',
                                       'bamboohr.employees.list',
                                       'onboarding_readiness'),
                                      ('offboarding-readiness-review',
                                       'Offboarding Readiness Review',
                                       'Identify employee exits that require '
                                       'coordinated access and service '
                                       'follow-up.',
                                       'bamboohr.employees.list',
                                       'offboarding_readiness'),
                                      ('policy-request-triage',
                                       'Policy Request Triage',
                                       'Prioritize people-policy related '
                                       'service requests using verified ticket '
                                       'context.',
                                       'freshservice.tickets.list',
                                       'policy_request_age'),
                                      ('employee-request-triage',
                                       'Employee Request Triage',
                                       'Analyze employee service requests and '
                                       'route attention to the highest-impact '
                                       'blockers.',
                                       'freshservice.tickets.get',
                                       'employee_request_age'),
                                      ('access-review-watch',
                                       'Access Review Watch',
                                       'Surface workforce records and service '
                                       'requests that indicate access-review '
                                       'gaps.',
                                       'bamboohr.employees.get',
                                       'access_review_gap'),
                                      ('device-service-risk-review',
                                       'Device & Service Risk Review',
                                       'Identify service records that may '
                                       'block employee productivity or device '
                                       'readiness.',
                                       'freshservice.tickets.list',
                                       'device_service_risk'),
                                      ('license-utilization-review',
                                       'License Utilization Review',
                                       'Prepare a workforce-based review of '
                                       'likely license allocation and '
                                       'deprovisioning needs.',
                                       'bamboohr.employees.list',
                                       'license_review_gap')]},
 'executive-command-center-3': {'title': 'Executive Command Center 3.0',
                                'department': 'Executive',
                                'skill_package': 'executive-command-skills',
                                'problem': 'Executives receive fragmented '
                                           'dashboards after problems occur '
                                           'rather than one evidence-backed '
                                           'view of cross-functional risk, '
                                           'action, and opportunity.',
                                'target': 'Create a daily operating view of '
                                          'revenue, cash, customers, service, '
                                          'marketing, and cross-functional '
                                          'priorities tied to verified source '
                                          'evidence.',
                                'connectors': ['hubspot',
                                               'quickbooks',
                                               'zendesk',
                                               'google_analytics'],
                                'optional': ['salesforce',
                                             'stripe',
                                             'freshservice',
                                             'slack'],
                                'profiles': {'hubspot': ['hubspot.deals.list',
                                                         'hubspot.companies.search'],
                                             'quickbooks': ['quickbooks.invoices.list',
                                                            'quickbooks.payments.list'],
                                             'zendesk': ['zendesk.tickets.list'],
                                             'google_analytics': ['google_analytics.reports.run']},
                                'agents': [('executive-intelligence-agent',
                                            'Executive Intelligence Agent'),
                                           ('cross-functional-risk-analyst',
                                            'Cross-Functional Risk Analyst')],
                                'kpis': [('revenue_risk',
                                          'Revenue at risk',
                                          'currency',
                                          'decrease'),
                                         ('cash_risk',
                                          'Cash risk',
                                          'currency',
                                          'decrease'),
                                         ('customer_risk',
                                          'Customer risk',
                                          'score',
                                          'decrease'),
                                         ('service_risk',
                                          'Service risk',
                                          'score',
                                          'decrease'),
                                         ('marketing_signal',
                                          'Marketing performance signal',
                                          'score',
                                          'increase'),
                                         ('operational_anomalies',
                                          'Operational anomalies',
                                          'count',
                                          'decrease'),
                                         ('priority_resolution',
                                          'Priority resolution rate',
                                          'percent',
                                          'increase')],
                                'plays': [('executive-morning-brief',
                                           'Executive Morning Brief',
                                           'Summarize the material operating '
                                           'changes requiring executive '
                                           'attention.',
                                           'hubspot.deals.list',
                                           'revenue_risk'),
                                          ('revenue-risk-watch',
                                           'Revenue Risk Watch',
                                           'Surface current pipeline and '
                                           'account evidence that threatens '
                                           'revenue.',
                                           'hubspot.companies.search',
                                           'revenue_risk'),
                                          ('cash-risk-watch-executive',
                                           'Cash Risk Watch',
                                           'Surface receivables and payment '
                                           'evidence that may affect near-term '
                                           'cash.',
                                           'quickbooks.invoices.list',
                                           'cash_risk'),
                                          ('customer-risk-watch-executive',
                                           'Customer Risk Watch',
                                           'Summarize current customer-support '
                                           'risk from service evidence.',
                                           'zendesk.tickets.list',
                                           'customer_risk'),
                                          ('service-risk-watch',
                                           'Service Risk Watch',
                                           'Identify service workload signals '
                                           'that warrant leadership attention.',
                                           'zendesk.tickets.list',
                                           'service_risk'),
                                          ('marketing-signal-watch',
                                           'Marketing Signal Watch',
                                           'Summarize material demand and '
                                           'engagement changes from analytics '
                                           'evidence.',
                                           'google_analytics.reports.run',
                                           'marketing_signal'),
                                          ('cross-functional-priority-review',
                                           'Cross-Functional Priority Review',
                                           'Rank the most material '
                                           'cross-functional issues and assign '
                                           'decision urgency.',
                                           'quickbooks.payments.list',
                                           'priority_resolution')]}}

SKILL_PACKS = {'people-it-operations-skills': {'skills': ['onboarding-readiness',
                                            'offboarding-readiness',
                                            'policy-analysis',
                                            'employee-request-triage',
                                            'access-review',
                                            'device-compliance-analysis',
                                            'license-utilization-analysis']},
 'executive-command-skills': {'skills': ['executive-briefing',
                                         'revenue-risk-analysis',
                                         'cash-risk-analysis',
                                         'customer-risk-analysis',
                                         'service-risk-analysis',
                                         'operational-anomaly-analysis',
                                         'cross-functional-prioritization']}}

def _tool_step(step_id: str, action: str, connector: str) -> dict[str, Any]:
    return {
        "id": step_id,
        "name": action.replace(".", " ").replace("_", " ").title(),
        "type": "invoke_tool",
        "config": {
            "action": action,
            "tool_action": action,
            "vendor": connector,
            "connector": connector,
            "selectedAction": action.split(".", 1)[-1],
            "selected_action": action.split(".", 1)[-1],
        },
        "requires_connector": connector,
    }

def _agent_step(step_id: str, seed: str, task: str) -> dict[str, Any]:
    return {"id": step_id, "name": "Analyze evidence", "type": "agent", "metadata": {"agent_seed": seed, "task": task, "briefing_from_steps": True}}

def _connector_for_action(action: str) -> str:
    return action.split(".", 1)[0]

def build_department_outcome_pack_config(slug: str) -> dict[str, Any]:
    spec = PACK_SPECS[slug]
    skill_slug = spec["skill_package"]
    skill_requirements = list(SKILL_PACKS[skill_slug]["skills"])
    agent_seeds = [f"agent:{key}" for key, _ in spec["agents"]]
    kpis = [
        {"key": key, "label": label, "unit": unit, "direction": direction, "source": "verified_department_dataset"}
        for key, label, unit, direction in spec["kpis"]
    ]
    plays = []
    for index, (key, name, desc, action, kpi_key) in enumerate(spec["plays"]):
        agent_seed = agent_seeds[index % len(agent_seeds)]
        plays.append({
            "key": key,
            "name": name,
            "description": desc,
            "trigger": {"type": "scheduled", "cadence": "daily"} if index else {"type": "scheduled", "cadence": "hourly"},
            "workflow_steps": [
                _tool_step(f"{key}-evidence", action, _connector_for_action(action)),
                _agent_step(f"{key}-analysis", agent_seed, f"{desc} Use only connector evidence; distinguish facts, inference, and missing data."),
            ],
            "outcome_events": [f"{key.replace('-', '_')}_reviewed"],
            "kpi_keys": [kpi_key],
            "approvals": [],
            "verification": {"mode": "source_of_record", "provider_acceptance_is_terminal": False},
            "runtime_inputs": [],
        })

    profiles = [
        {"provider": provider, "status": "implementation", "actions": actions}
        for provider, actions in spec["profiles"].items()
    ]
    agents = [
        {
            "seed_label": f"agent:{key}",
            "name": name,
            "purpose": f"Operate {spec['department']} evidence review and measurable decision support.",
            "role": name,
            "department": spec["department"],
            "capabilities": skill_requirements,
            "systems": list(spec["connectors"] + spec["optional"]),
        }
        for key, name in spec["agents"]
    ]
    knowledge = [
        {"seed_label": f"{slug}:policy", "title": f"{spec['title']} Policy & SOP", "type": "manual", "metadata": {"purpose": "Department policy, thresholds, approvals, and SOPs."}},
        {"seed_label": f"{slug}:playbook", "title": f"{spec['title']} Operating Playbook", "type": "manual", "metadata": {"purpose": "Operating definitions, escalation rules, and decision guidance."}},
    ]
    dataset = {
        "entities": [
            {"name": "department_records", "source": "connected_systems", "primary_key": "record_id", "fields": ["record_id","account_id","status","owner","created_at","updated_at"]},
            {"name": "verified_outcomes", "source": "gravitre_verified_outcomes", "primary_key": "outcome_id", "fields": ["outcome_id","play_key","status","verified_at","metric_delta"]},
        ],
        "metrics": [{"key": key, "label": label, "formula": f"unmeasured:{key}", "unit": unit} for key, label, unit, _ in spec["kpis"]],
    }
    dashboard = {
        "title": f"{spec['title']} Command Center",
        "refresh_mode": "event",
        "metrics": [
            {"kpi_key": key, "label": label, "visualization": "trend" if unit not in {"count","currency"} else "metric", "description": f"Verified Marketplace 3.0 KPI: {label}."}
            for key, label, unit, _ in spec["kpis"]
        ],
    }
    return {
        "marketplace_version": "3.0",
        "outcome_contract": {
            "problem": spec["problem"],
            "target_outcome": spec["target"],
            "baseline_metric": spec["kpis"][0][0],
            "success_criteria": [
                "All included Plays install into Gravitre's canonical Play/workflow runtime.",
                "Every Play reads only registered source-of-record actions in the declared read-only profile.",
                "Every declared KPI is represented in the installed dashboard and normalized dataset.",
                "At least one declared outcome event must be measured before Outcome Verified status is earned.",
            ],
            "outcome_events": [f"{key.replace('-', '_')}_reviewed" for key, *_ in spec["plays"]],
            "kpis": kpis,
            "verification_required": True,
        },
        "agents": agents,
        "plays": plays,
        "knowledge": knowledge,
        "dataset": dataset,
        "dashboard": dashboard,
        "skills": [skill_slug],
        "skill_requirements": skill_requirements,
        "skill_bindings": {skill: skill_slug for skill in skill_requirements},
        "runtime_profiles": profiles,
        "connector_alternatives": [[name] for name in spec["connectors"]] + [[name for name in spec["optional"]]],
    }
