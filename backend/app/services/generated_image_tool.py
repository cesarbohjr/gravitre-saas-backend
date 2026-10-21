"""Image generation executor on the canonical audited WRITE spine."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from app.core.async_bridge import run_coro_sync
from app.ml.generative_models import DiffusionModelConnector
from app.services.tool_types import NormalizedResult, ToolContext, ToolPermissionDeniedError

ACTION = "assistant.generate_image"


def execute_generate_image(ctx: ToolContext, params: dict) -> NormalizedResult:
    from app.services.write_authority import check_write_authority
    # Paid generation never inherits the legacy global shadow/off bypass.
    authority = check_write_authority(ACTION, settings=SimpleNamespace(write_authority_mode="enforce"),
                                      org_id=ctx.org_id, actor_id=ctx.actor_id)
    if authority is None or authority.kind not in {"human", "run"} or not authority.ref:
        raise ToolPermissionDeniedError("An explicit image request or approved workflow run is required")
    turn = ctx.turn_id or ctx.run_id
    if not turn or not ctx.actor_id or ctx.actor_id == "system":
        raise ToolPermissionDeniedError("Authenticated actor and durable turn/run identity required")
    operation = str(uuid5(NAMESPACE_URL, f"gravitre:image:{ctx.org_id}:{turn}:{ctx.step_id or 'image'}"))
    result = run_coro_sync(DiffusionModelConnector().generate(org_id=ctx.org_id, actor_id=ctx.actor_id,
        prompt=params.get("prompt"), operation_id=operation, settings=ctx.settings), timeout=150)
    if result.get("status") != "ok":
        return NormalizedResult(success=False, action=ACTION, data=result,
                                error_code="outcome_uncertain", error_message=result.get("reason"))
    return NormalizedResult(success=True, action=ACTION, data=result)
