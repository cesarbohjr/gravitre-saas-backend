#!/usr/bin/env python3
"""Rebuild the review queue from routes and locally imported UI source files.

This is static discovery, not a browser audit or a count of visible controls.
Dynamic imports expressed as literals are included; computed imports are not.
"""
import re
from collections import Counter
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web"
OUT = ROOT / "docs/design/3.0-plus"
IMPORT = re.compile(r'(?:from\s+|import\s*\(\s*)[\'"]([^\'"]+)[\'"]')
SURFACE = re.compile(r'<([A-Z][\w.]*(?:Dialog|Sheet|Modal|Popover|DropdownMenu|Drawer|Inspector|Window)[\w.]*|(?:Dialog|Sheet|Popover|DropdownMenu|Drawer))\b')
CONTROL = re.compile(r'<(?:button|Button|Input|input|Select|select|Switch|Textarea|textarea|TabsTrigger|DropdownMenuItem)\b')
FAMILIES = {
    "marketplace": "Discover", "plays": "Discover",
    "intelligence": "Understand", "metrics": "Understand", "analytics": "Understand",
    "agents": "Manage", "connectors": "Manage", "sources": "Manage", "integrations": "Manage",
    "models": "Manage", "environments": "Manage", "settings": "Create", "admin": "Manage",
    "activity": "Operate", "approvals": "Operate", "notifications": "Operate", "audit": "Operate",
    "schedules": "Operate", "workflows": "Operate", "runs": "Operate", "tasks": "Operate",
    "assignments": "Operate", "goals": "Operate", "lite": "Operate", "training": "Create",
    "builder": "Create", "ai": "Create", "home": "Operate",
    "assistant": "Create", "chat": "Create", "operator": "Manage", "systems": "Manage",
    "deliverables": "Operate", "outcomes": "Understand", "multi-agent-run": "Operate",
    "platform": "Manage", "search": "Discover", "onboarding": "Create", "welcome": "Create",
    "desktop": "Manage", "extension": "Manage",
}

def resolve_import(owner, spec):
    if spec.startswith("@/"):
        base = WEB / spec[2:]
    elif spec.startswith("."):
        base = owner.parent / spec
    else:
        return None
    for candidate in [base, *[Path(str(base) + ext) for ext in (".tsx", ".ts", ".jsx", ".js")], base / "index.tsx", base / "index.ts"]:
        if candidate.is_file() and candidate.suffix in {".tsx", ".ts", ".jsx", ".js"}:
            return candidate.resolve()
    return None

@cache
def closure(start):
    found, pending = set(), [start]
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for spec in IMPORT.findall(path.read_text()):
            target = resolve_import(path, spec)
            if target and target not in found:
                pending.append(target)
    return found

rows, ui = [], {}
for path in sorted(p for p in (WEB / "app").rglob("page.*") if p.suffix in {".tsx", ".jsx", ".ts", ".js"}):
    parts = [part for part in path.parent.relative_to(WEB / "app").parts if not part.startswith("(")]
    route = "/" + "/".join(parts)
    source = path.read_text()
    scope = "Product" if parts and parts[0] in FAMILIES else "Public/auth/support — classify"
    if parts and parts[0] in {"e2e", "dev", "test"}:
        scope = "Fixture/development"
    family = FAMILIES.get(parts[0] if parts else "", "Review")
    if any(part in {"admin", "org-admin", "platform-admin", "publisher", "installed"} for part in parts):
        family = "Manage"
    if "analytics" in parts or "results" in parts:
        family = "Understand"
    if any(part in {"billing", "submit", "sandbox"} for part in parts):
        family = "Create"
    if "builder" in parts or "new" in parts or "model-studio" in parts:
        family = "Create"
    level = "Primary" if len(parts) <= 1 else "Secondary/nested"
    redirects = re.findall(r'\b(?:redirect|permanentRedirect)\(\s*[\'"]([^\'"]+)', source)
    components = set(closure(path.resolve()))
    # Next composes these files implicitly; ordinary import traversal misses them.
    ancestor = path.parent
    while ancestor.is_relative_to(WEB / "app"):
        for stem in ("layout", "template", "loading", "error", "not-found", "global-error"):
            for ext in (".tsx", ".ts", ".jsx", ".js"):
                implicit = ancestor / (stem + ext)
                if implicit.is_file():
                    components.update(closure(implicit.resolve()))
        if ancestor == WEB / "app":
            break
        ancestor = ancestor.parent
    surface_files = []
    for component in components:
        text = component.read_text()
        surfaces = sorted(set(SURFACE.findall(text)))
        controls = len(CONTROL.findall(text))
        if surfaces or controls:
            rel = component.relative_to(ROOT).as_posix()
            surface_files.append(rel)
            entry = ui.setdefault(rel, {"surfaces": surfaces, "controls": controls, "routes": set()})
            entry["routes"].add(route)
    rows.append((route, level, scope, family, ", ".join(redirects) or "—", len(surface_files), path.relative_to(ROOT).as_posix()))

OUT.mkdir(parents=True, exist_ok=True)
lines = ["# Design surface review queue", "", "Generated with `python3 scripts/inventory-design-surfaces.py`.", "",
    "This inventory discovers routes and reachable local JSX controls/disclosures, including ancestor layouts, templates and loading/error/not-found boundaries composed by Next. Counts are source occurrences, not rendered buttons. Shared chrome can be reachable from many routes. Dynamic conditions, permissions, runtime tabs, computed imports and backend authorization require manual review. Family assignments are a starting hypothesis, especially for mixed discovery/setup routes.", "",
    "**Visual acceptance: NOT RUN.** A listed file is not an accepted surface. Read each route and its reachable UI, then record browser evidence at 1440 / 834 / 390 including empty, error, loading, selected, pending and permission states.", "",
    f"Discovered {len(rows)} page routes and {len(ui)} reachable files containing controls or disclosures.", "",
    "| Route | Level | Scope | Proposed family | Redirect expression | UI files | Source |", "|---|---|---|---|---|---:|---|"]
for row in rows:
    lines.append("| " + " | ".join(str(value) for value in row) + " |")
lines += ["", "## Tertiary disclosures and control sources", "",
    "Use this index to follow windows, inspectors, popovers, dialogs and action controls beyond the page level. Full JSX lists include primitive wrappers; opening a wrapper does not establish a functional or visible surface.", "",
    "| Source | Disclosure components | Control occurrences | Reachable routes |", "|---|---|---:|---:|"]
for path, entry in sorted(ui.items()):
    lines.append(f"| {path} | {', '.join(entry['surfaces']) or '—'} | {entry['controls']} | {len(entry['routes'])} |")
(OUT / "18-design-surface-review-queue.md").write_text("\n".join(lines) + "\n")
print(f"{len(rows)} routes; {len(ui)} control/disclosure source files; {dict(Counter(row[2] for row in rows))}")
