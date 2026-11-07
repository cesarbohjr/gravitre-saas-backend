"""Static workflow risk scanner: no external network or credentials."""
from pathlib import Path
from runpy import run_path

# Load by absolute source path: the test package may shadow backend/scripts.
inventory = run_path(str(Path(__file__).resolve().parents[2] / 'scripts' / 'master_qa_workflow_audit.py'), run_name='master_qa_audit')['inventory']


def test_inventory_captures_callers_and_redacts_values(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "child.yml").write_text(
        "name: Child\non:\n  workflow_call:\njobs:\n  task:\n    runs-on: ubuntu-latest\n"
    )
    (wf / "parent.yml").write_text(
        "name: Parent\non:\n  pull_request:\n  workflow_dispatch:\njobs:\n"
        "  invoke:\n    uses: ./.github/workflows/child.yml\n"
        "    secrets: inherit\n"
        "  deploy:\n    runs-on: ubuntu-latest\n    environment: production\n"
        "    steps:\n      - run: echo ${{ secrets.INTERNAL_SECRET_NAME }}\n"
    )
    result = inventory(tmp_path)
    assert result["source_workflow_count"] == 2
    child, parent = result["workflows"]
    assert child["known_local_callers"] == [".github/workflows/parent.yml"]
    assert parent["workflow_call_dependencies"] == ["./.github/workflows/child.yml"]
    assert parent["referenced_secret_names_only"] == ["INTERNAL_SECRET_NAME"]
    assert "production" in parent["job_environment_tokens"]
    assert parent["static_production_side_effect_risk"] == "REVIEW_REQUIRED"
    assert parent["actual_spend"] is None
    assert not parent["retirement_authorized"]


def test_unknown_cost_and_required_checks_are_never_inferred(tmp_path):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "safe.yml").write_text(
        "name: Safe\non:\n  pull_request:\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
    )
    result = inventory(tmp_path)
    assert result["workflows"][0]["disposition"] == "INVESTIGATE"
    assert result["workflows"][0]["required_check_state"].startswith("UNKNOWN")
    assert result["workflows"][0]["active_status"].startswith("UNKNOWN")
    assert result["workflows"][0]["runtime_minutes"] is None
    assert result["workflows"][0]["static_network_or_provider_risk"] == "NOT_ESTABLISHED"
