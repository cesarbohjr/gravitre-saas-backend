import os

base = os.path.join(os.path.dirname(__file__), "..", "apps", "web", "app")
base = os.path.normpath(base)

routes = [
    ("agents", "detail", "AI Team", "Manage AI agents, profiles, and team capabilities.", "/agents"),
    ("ai", "chat", "Gravitre AI", "Unified AI surface for execute, chat, and search.", "/ai"),
    ("approvals", "table", "Approvals", "Review and action pending approval requests.", "/approvals"),
    ("assignments", "table", "Assignments", "Assign work to AI agents and track deliverables.", "/assignments"),
    ("assistant", "chat", "Workspace Chat", "Multi-turn workspace chat with tools and saved threads.", "/assistant"),
    ("audit", "table", "History", "Audit trail of workspace actions and changes.", "/audit"),
    ("chat", "chat", "Chat", "Workspace chat conversations.", "/chat"),
    ("connectors", "table", "Connectors", "Connect external systems and integrations.", "/connectors"),
    ("deliverables", "table", "Deliverables", "Goal deliverables and outputs from agent work.", "/deliverables"),
    ("environments", "dashboard", "Environments", "Manage deployment environments.", "/environments"),
    ("goals", "dashboard", "Goals", "Track goals and outcomes across your org.", "/goals"),
    ("integrations", "table", "Integrations", "Integration settings and connections.", "/integrations"),
    ("lite", "dashboard", "Gravitre Lite", "Simplified workspace for department users.", "/lite"),
    ("marketplace", "dashboard", "Marketplace", "Browse and install department packs and AI assets.", "/marketplace"),
    ("metrics", "dashboard", "Metrics", "Operational metrics and performance dashboards.", "/metrics"),
    ("models", "table", "Model Registry", "Configure and manage ML models.", "/models"),
    ("notifications", "table", "Notifications", "Notification preferences and history.", "/notifications"),
    ("onboarding", "dashboard", "Onboarding", "Complete org onboarding setup.", "/onboarding"),
    ("operator", "chat", "Command Center", "Delegate tasks and track async operator work.", "/command-center"),
    ("runs", "table", "Runs", "Workflow and agent run history.", "/runs"),
    ("schedules", "table", "Schedules", "Scheduled workflow and automation runs.", "/schedules"),
    ("search", "chat", "Universal Search", "Search workflows, agents, connectors, and records.", "/search"),
    ("settings", "dashboard", "Settings", "Workspace, team, security, and AI settings.", "/settings"),
    ("sources", "table", "Sources", "Knowledge sources and document ingestion.", "/sources"),
    ("systems", "table", "Systems", "Connected systems overview.", "/systems"),
    ("tasks", "table", "Tasks", "Task queue and assignment tracking.", "/tasks"),
    ("training", "table", "Agent Training", "Train and fine-tune agent behavior.", "/training"),
    ("workflows", "table", "Workflows", "Build, monitor, and run automations.", "/workflows"),
]

loading_tpl = '''import {{ RouteLoading }} from "@/components/gravitre/route-loading"

export default function Loading() {{
  return <RouteLoading variant="{variant}" />
}}
'''

error_tpl = '''"use client"

export { default } from "@/components/gravitre/route-error"
'''

layout_tpl = '''import type {{ Metadata }} from "next"
import {{ authenticatedMetadata }} from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "{title} | Gravitre",
  "{desc}",
  {{ canonical: "{canonical}" }},
)

export default function Layout({{ children }}: {{ children: React.ReactNode }}) {{
  return children
}}
'''

counts = {"loading": 0, "error": 0, "layout": 0}

for d, variant, title, desc, canonical in routes:
    dirpath = os.path.join(base, d)
    if not os.path.isdir(dirpath):
        continue
    lp = os.path.join(dirpath, "loading.tsx")
    if not os.path.exists(lp):
        with open(lp, "w", encoding="utf-8") as f:
            f.write(loading_tpl.format(variant=variant))
        counts["loading"] += 1
    ep = os.path.join(dirpath, "error.tsx")
    if not os.path.exists(ep):
        with open(ep, "w", encoding="utf-8") as f:
            f.write(error_tpl)
        counts["error"] += 1
    lay = os.path.join(dirpath, "layout.tsx")
    if not os.path.exists(lay):
        with open(lay, "w", encoding="utf-8") as f:
            f.write(layout_tpl.format(title=title, desc=desc, canonical=canonical))
        counts["layout"] += 1

for d, variant in [("command-center", "chat"), ("multi-agent-run", "dashboard")]:
    dirpath = os.path.join(base, d)
    if not os.path.isdir(dirpath):
        continue
    lp = os.path.join(dirpath, "loading.tsx")
    if not os.path.exists(lp):
        with open(lp, "w", encoding="utf-8") as f:
            f.write(loading_tpl.format(variant=variant))
        counts["loading"] += 1
    ep = os.path.join(dirpath, "error.tsx")
    if not os.path.exists(ep):
        with open(ep, "w", encoding="utf-8") as f:
            f.write(error_tpl)
        counts["error"] += 1

for d in ["home", "welcome", "intelligence"]:
    dirpath = os.path.join(base, d)
    if not os.path.isdir(dirpath):
        continue
    ep = os.path.join(dirpath, "error.tsx")
    if not os.path.exists(ep):
        with open(ep, "w", encoding="utf-8") as f:
            f.write(error_tpl)
        counts["error"] += 1

admin = os.path.join(base, "admin")
if os.path.isdir(admin):
    lp = os.path.join(admin, "loading.tsx")
    if not os.path.exists(lp):
        with open(lp, "w", encoding="utf-8") as f:
            f.write(loading_tpl.format(variant="dashboard"))
        counts["loading"] += 1
    ep = os.path.join(admin, "error.tsx")
    if not os.path.exists(ep):
        with open(ep, "w", encoding="utf-8") as f:
            f.write(error_tpl)
        counts["error"] += 1
    lay = os.path.join(admin, "layout.tsx")
    if not os.path.exists(lay):
        with open(lay, "w", encoding="utf-8") as f:
            f.write(
                layout_tpl.format(
                    title="Admin",
                    desc="Administrative intelligence and org learning.",
                    canonical="/admin",
                )
            )
        counts["layout"] += 1

print(counts)
