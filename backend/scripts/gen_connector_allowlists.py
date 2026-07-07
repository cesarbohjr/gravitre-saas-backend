"""Generate app/services/connector_allowlists.py from current catalog state."""
from __future__ import annotations

from pathlib import Path

ORPHANS = (
    "fhir.appointments.search",
    "fhir.patients.get",
    "fhir.patients.search",
    "fhir.prior_auth.checklist",
    "jira.users.search",
    "quickbooks.accounts.list",
    "quickbooks.bills.get",
    "quickbooks.customers.get",
    "quickbooks.payments.list",
    "quickbooks.vendors.get",
    "quickbooks.vendors.list",
    "salesforce.accounts.create",
    "webhook.post",
    "zendesk.tickets.close",
)

API_IMPORTS = (
    "app/services/connector_action_workflows.py",
    "app/services/connector_parameter_inference.py",
    "app/routers/connectors.py",
    "app/connectors/connection_health.py",
    "app/services/outcome_attribution_service.py",
    "app/services/post_publish_marketing_metrics_service.py",
)


def _render_frozenset(name: str, entries: tuple[str, ...]) -> list[str]:
    lines = [f"{name}: frozenset[str] = frozenset(", "    {"]
    lines.extend(f'        "{entry}",' for entry in entries)
    lines.extend(["    }", ")"])
    return lines


def _pending_workflow_schema_actions() -> tuple[str, ...]:
    from app.connectors.action_catalog.action_workflow_schema import get_workflow_schema
    from app.connectors.action_catalog.registry import all_catalog_action_specs

    return tuple(
        sorted(
            spec.id
            for spec in all_catalog_action_specs()
            if spec.kind == "write" and not get_workflow_schema(spec.id)
        )
    )


def main() -> None:
    pending = _pending_workflow_schema_actions()

    parts = [
        '"""Explicit governance debt allowlists — shrink by removing entries after fixing debt."""',
        "from __future__ import annotations",
        "",
        *_render_frozenset("ORPHAN_HANDLER_ALLOWLIST", ORPHANS),
        "",
        *_render_frozenset("API_IMPORT_EXCEPTION_ALLOWLIST", API_IMPORTS),
        "",
        *_render_frozenset("PENDING_WORKFLOW_SCHEMA_ALLOWLIST", pending),
        "",
    ]
    out = Path("app/services/connector_allowlists.py")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {out} pending={len(pending)}")


if __name__ == "__main__":
    main()
