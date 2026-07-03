"""Add loading.tsx and error.tsx to nested route dirs that have page.tsx but lack shells."""
from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "web" / "app"

SKIP_PARTS = {"api", "auth", "(marketing)"}

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

NESTED_LAYOUTS: dict[str, tuple[str, str, str]] = {
    "settings/billing": ("Billing", "Manage subscription, usage, and invoices.", "/settings/billing"),
    "settings/billing/checkout": ("Checkout", "Complete your billing checkout.", "/settings/billing/checkout"),
    "settings/profile": ("Profile", "Your account profile and preferences.", "/settings/profile"),
    "settings/organizations": ("Organizations", "Manage organization membership and invites.", "/settings/organizations"),
    "settings/federation": ("Federation", "Cross-org federation settings.", "/settings/federation"),
    "settings/enterprise": ("Enterprise", "Enterprise branding and controls.", "/settings/enterprise"),
    "runs/[id]": ("Run details", "Workflow run execution trace and status.", "/runs"),
    "workflows/[id]": ("Workflow", "Workflow definition and run history.", "/workflows"),
    "workflows/[id]/builder": ("Workflow builder", "Visual workflow builder.", "/workflows"),
    "workflows/[id]/schedules": ("Workflow schedules", "Scheduled runs for this workflow.", "/workflows"),
    "workflows/failure-predictions": ("Failure alerts", "Predicted workflow failures.", "/workflows/failure-predictions"),
    "agents/[id]": ("Agent profile", "Agent capabilities, memory, and performance.", "/agents"),
    "agents/[id]/chat": ("Agent chat", "Chat with a dedicated agent.", "/agents"),
    "agents/[id]/memory": ("Agent memory", "Memories stored by this agent.", "/agents"),
    "agents/[id]/knowledge": ("Agent knowledge", "Knowledge sources for this agent.", "/agents"),
    "agents/new": ("New agent", "Create a new AI agent.", "/agents/new"),
    "marketplace/assets": ("Marketplace catalog", "Browse marketplace assets.", "/marketplace/assets"),
    "marketplace/assets/[slug]": ("Marketplace asset", "Asset details and installation.", "/marketplace"),
    "marketplace/analytics": ("Marketplace analytics", "Catalog adoption and usage.", "/marketplace/analytics"),
    "marketplace/analytics/roi": ("Marketplace ROI", "Estimated ROI from installed packs.", "/marketplace/analytics/roi"),
    "marketplace/billing": ("Publisher billing", "Marketplace earnings and pricing.", "/marketplace/billing"),
    "marketplace/publisher/analytics": ("Publisher analytics", "Publisher revenue and installs.", "/marketplace/publisher/analytics"),
    "marketplace/installed": ("Installed assets", "Assets deployed in your org.", "/marketplace/installed"),
    "assignments/[id]": ("Assignment", "Assignment details and deliverables.", "/assignments"),
    "sources/[id]": ("Source", "Knowledge source schema and sync.", "/sources"),
    "models/[id]": ("Model", "Model configuration and metrics.", "/models"),
    "intelligence/agents/[id]": ("Agent intelligence", "Agent intelligence profile.", "/intelligence/agents"),
}


def should_skip(path: Path) -> bool:
    rel = path.relative_to(APP_ROOT).as_posix()
    if rel.startswith("("):
        return True
    for part in SKIP_PARTS:
        if part in rel.split("/"):
            return True
    return False


def pick_variant(rel: str) -> str:
    lower = rel.lower()
    if "chat" in lower or lower.endswith("/assistant"):
        return "chat"
    if "builder" in lower:
        return "detail"
    if any(token in lower for token in ("[id]", "[slug]", "[name]", "/new")):
        return "detail"
    if any(token in lower for token in ("analytics", "billing", "audit", "runs", "schedules", "tasks", "sandbox")):
        return "table"
    return "dashboard"


def main() -> None:
    counts = {"loading": 0, "error": 0, "layout": 0}

    for dirpath, _, files in os.walk(APP_ROOT):
        if "page.tsx" not in files:
            continue
        path = Path(dirpath)
        if should_skip(path):
            continue

        rel = path.relative_to(APP_ROOT).as_posix()
        variant = pick_variant(rel)

        loading_path = path / "loading.tsx"
        if not loading_path.exists():
            loading_path.write_text(loading_tpl.format(variant=variant), encoding="utf-8")
            counts["loading"] += 1

        error_path = path / "error.tsx"
        if not error_path.exists():
            error_path.write_text(error_tpl, encoding="utf-8")
            counts["error"] += 1

        if rel in NESTED_LAYOUTS and not (path / "layout.tsx").exists():
            title, desc, canonical = NESTED_LAYOUTS[rel]
            path.joinpath("layout.tsx").write_text(
                layout_tpl.format(title=title, desc=desc, canonical=canonical),
                encoding="utf-8",
            )
            counts["layout"] += 1

    print(counts)


if __name__ == "__main__":
    main()
