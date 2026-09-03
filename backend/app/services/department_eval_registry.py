"""Department eval registry — consolidates real pack + security + withhold gates.

Departments map to real intelligence packs / vertical tooling already in-repo.
Legal has no Intelligence Pack yet; it uses Clio tooling + permission/security gates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DepartmentEvalSpec:
    department: str
    label: str
    pack_id: str | None
    """Intelligence pack id when one exists; None for vertical-only (Legal)."""
    expected_systems: tuple[str, ...] = ()
    """Connector/system ids that must appear on the pack or be registered actions."""
    pytest_globs: tuple[str, ...] = ()
    """Existing pytest paths that must stay green for this department."""
    dimensions: tuple[str, ...] = (
        "knowledge_accuracy",
        "retrieval_citation",
        "calculation",
        "tool_selection",
        "permission_compliance",
        "action_correctness",
        "security_injection",
        "hallucination_withhold",
        "honest_refusal",
    )


DEPARTMENT_EVAL_SPECS: tuple[DepartmentEvalSpec, ...] = (
    DepartmentEvalSpec(
        department="marketing",
        label="Marketing",
        pack_id="marketing-intelligence-pack",
        expected_systems=("google_search_console", "google_analytics", "hubspot"),
        pytest_globs=(
            # Concrete pack gate (no bare test_marketing_pack.py; glob expanded by runner).
            "tests/marketplace/test_marketing_pack_mode_ab_decision.py",
            "tests/services/test_routing_nl_variance_battery.py",
        ),
    ),
    DepartmentEvalSpec(
        department="sales",
        label="Sales",
        pack_id="sales-intelligence-pack",
        expected_systems=("hubspot", "apollo"),
        pytest_globs=("tests/marketplace/test_sales_pack.py",),
    ),
    DepartmentEvalSpec(
        department="finance",
        label="Finance",
        pack_id="finance-intelligence-pack",
        expected_systems=("quickbooks",),
        pytest_globs=("tests/marketplace/test_finance_pack.py",),
    ),
    DepartmentEvalSpec(
        department="legal",
        label="Legal",
        pack_id=None,
        expected_systems=("clio",),
        pytest_globs=("tests/services/test_clio_tools.py",),
    ),
    DepartmentEvalSpec(
        department="hr",
        label="HR",
        pack_id="hr-talent-intelligence-pack",
        expected_systems=("workday",),
        pytest_globs=("tests/marketplace/test_hr_talent_pack.py",),
    ),
    DepartmentEvalSpec(
        department="msp",
        label="MSP / Cyber",
        pack_id="msp-intelligence-pack",
        expected_systems=("apollo", "hubspot", "nvd"),
        pytest_globs=(
            "tests/marketplace/test_msp_pack.py",
            "tests/services/test_routing_nl_variance_battery.py",
        ),
    ),
)


def get_department_eval_spec(department: str) -> DepartmentEvalSpec | None:
    key = (department or "").strip().lower()
    for spec in DEPARTMENT_EVAL_SPECS:
        if spec.department == key:
            return spec
    return None


def list_department_eval_specs() -> list[DepartmentEvalSpec]:
    return list(DEPARTMENT_EVAL_SPECS)


def department_eval_manifest() -> dict[str, Any]:
    """Machine-readable inventory for CI + docs."""
    return {
        "suite": "department-eval",
        "version": 1,
        "departments": [
            {
                "department": s.department,
                "label": s.label,
                "packId": s.pack_id,
                "expectedSystems": list(s.expected_systems),
                "pytestGlobs": list(s.pytest_globs),
                "dimensions": list(s.dimensions),
            }
            for s in DEPARTMENT_EVAL_SPECS
        ],
    }
