"""STA-135 / AI-005: Graph-native workflow execution engine.

Executes builder graphs (nodes + edges) in topological batches so each node
receives full upstream outputs before it runs. Integrates with the same run/step
logging primitives as ``execute.py``.
"""
from __future__ import annotations

from app.workflows.graph_model import (  # noqa: F401  (re-exported public API)
    _APPROVAL_NODE_TYPES,
    _CHECKPOINT_KEY,
    _PASSTHROUGH_NODE_TYPES,
    ExecutionGraph,
    GraphValidationError,
    _edges_as_dicts,
    _upstream_outputs,
    build_execution_graph,
    topological_batches,
    validate_execution_graph,
)
from app.workflows.execution_engine_runtime import (
    execute_workflow_graph,
    resolve_approval_batch_and_resume,
    resume_paused_workflow_graph,
    resume_workflow_graph,
    retry_workflow_step,
)
