"""Phase D — mandatory agent benchmark scenario registry (A–J + harness regressions)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

ScenarioFn = Callable[[], None]


@dataclass(frozen=True)
class BenchmarkScenario:
    scenario_id: str
    layer: str
    description: str
    pytest_node: str


MANDATORY_SCENARIOS: tuple[BenchmarkScenario, ...] = (
    BenchmarkScenario("A", "resolution", "GA4 traffic single property auto-select", "test_scenario_a_ga4_traffic_single_property_auto_select"),
    BenchmarkScenario("B", "resolution", "Website doing identifies analytics capabilities", "test_scenario_b_website_doing_identifies_analytics_capabilities"),
    BenchmarkScenario("C", "reference", "Yes confirms pending offered action", "test_scenario_c_yes_confirms_pending_offered_action"),
    BenchmarkScenario("D", "reference", "All 3 selects all options", "test_scenario_d_all_three_selects_all_options"),
    BenchmarkScenario("E", "reference", "That resolves prior analysis", "test_scenario_e_that_resolves_prior_analysis"),
    BenchmarkScenario("F", "clarification", "Multiple GA properties clarify when ambiguous", "test_scenario_f_multiple_ga_properties_clarify_only_when_ambiguous"),
    BenchmarkScenario("G", "connector", "No GA connection clear message", "test_scenario_g_no_ga_connection_clear_message"),
    BenchmarkScenario("H", "semantic", "GA alias", "test_scenario_h_i_j_alias_resolution[GA-google_analytics]"),
    BenchmarkScenario("I", "semantic", "QBO alias", "test_scenario_h_i_j_alias_resolution[QBO-quickbooks]"),
    BenchmarkScenario("J", "semantic", "SFDC alias", "test_scenario_h_i_j_alias_resolution[SFDC-salesforce]"),
    BenchmarkScenario("B-ingress", "ingress", "Chitchat skips resource resolution", "test_chitchat_skips_resource_resolution"),
    BenchmarkScenario("B-rag", "context", "Chitchat suppresses RAG slice", "test_chitchat_suppresses_rag_slice"),
    BenchmarkScenario("C-exec", "execution", "Cross-source plan GA4+GSC", "test_cross_source_plan_when_ga4_and_gsc_connected"),
    BenchmarkScenario("C-terminal", "compose", "Terminal policy blocks defer without pending", "test_terminal_policy_blocks_defer_without_pending"),
    BenchmarkScenario("D-trace", "trace", "Unified turn_id from task_state", "test_unify_turn_id_prefers_cognitive_trace"),
    BenchmarkScenario("D-blocks", "compose", "Structured blocks from GA4 metrics", "test_blocks_from_ga4_reports_renders_metrics"),
)


def list_mandatory_scenario_ids() -> list[str]:
    return [s.scenario_id for s in MANDATORY_SCENARIOS]


def scenarios_for_layer(layer: str) -> list[BenchmarkScenario]:
    return [s for s in MANDATORY_SCENARIOS if s.layer == layer]
