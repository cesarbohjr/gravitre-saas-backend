"""Opt-in ledger fixture for connector adapter tests with a mocked provider."""

from dataclasses import replace

from app.services.tool_types import ToolContext
from tests.scenarios.conversation_harness import ScenarioDB


def with_provider_write_ledger(ctx: ToolContext, connector_id: str) -> ToolContext:
    """Exercise the real RPC client contract using the scenario ledger."""
    ctx.client.rpc.side_effect = ScenarioDB().rpc
    return replace(ctx, connector_id=connector_id)
