"""Unified artifact registry for chat, connector, and orchestration results (Tier 3)."""
from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

_ARTIFACT_KINDS = frozenset({"document", "record", "run", "report", "workspace_file", "link"})


def _artifact_id(kind: str, seed: str) -> str:
    return f"{kind}:{seed}"


class ArtifactRegistryService:
    """Build and attach artifact cards from execution results."""

    def build_artifacts(self, result: Any) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        structured = dict(result.structured or {})

        if result.result_url:
            artifacts.append(
                {
                    "artifact_id": _artifact_id("link", result.entity_id or result.result_url),
                    "kind": "link",
                    "title": result.task_label or result.title or "Open result",
                    "preview": (result.body or "")[:240] or None,
                    "result_url": result.result_url,
                    "source": result.entity_type or "execution",
                    "integration": result.integration,
                }
            )

        if result.entity_type in {"run", "workflow_run"} or structured.get("runId"):
            run_id = str(structured.get("runId") or result.entity_id or "")
            artifacts.append(
                {
                    "artifact_id": _artifact_id("run", run_id or uuid4().hex),
                    "kind": "run",
                    "title": result.title or "Workflow run",
                    "preview": (result.body or "")[:240] or None,
                    "result_url": result.result_url,
                    "source": "workflow",
                    "metadata": {"runId": run_id, "workflowId": structured.get("workflowId")},
                }
            )

        if structured.get("format") == "markdown" or structured.get("content"):
            content = str(structured.get("content") or result.body or "")
            artifacts.append(
                {
                    "artifact_id": _artifact_id("document", structured.get("title") or result.title or "doc"),
                    "kind": "document",
                    "title": str(structured.get("title") or result.title or "Generated document"),
                    "preview": content[:280] or None,
                    "mime_type": "text/markdown",
                    "source": "generate_document",
                    "metadata": {"wordCount": structured.get("wordCount")},
                }
            )

        if result.entity_type == "connector" and result.success:
            artifacts.append(
                {
                    "artifact_id": _artifact_id("record", result.entity_id or result.integration or "connector"),
                    "kind": "record",
                    "title": result.task_label or result.title or "Connector result",
                    "preview": (result.body or "")[:240] or None,
                    "result_url": result.result_url,
                    "source": "connector",
                    "integration": result.integration,
                }
            )

        workspace_files = structured.get("workspaceFiles") or structured.get("workspace_files")
        if isinstance(workspace_files, dict):
            for path, content in list(workspace_files.items())[:5]:
                artifacts.append(
                    {
                        "artifact_id": _artifact_id("workspace_file", str(path)),
                        "kind": "workspace_file",
                        "title": str(path),
                        "preview": str(content)[:200] if content else None,
                        "source": "job_workspace",
                    }
                )

        codeact = structured.get("codeact") if isinstance(structured.get("codeact"), dict) else None
        if codeact and codeact.get("preview"):
            artifacts.append(
                {
                    "artifact_id": _artifact_id("report", "codeact"),
                    "kind": "report",
                    "title": codeact.get("description") or "Code transform result",
                    "preview": str(codeact.get("preview"))[:280],
                    "source": "codeact",
                }
            )

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in artifacts:
            aid = str(row.get("artifact_id") or "")
            if not aid or aid in seen:
                continue
            kind = str(row.get("kind") or "link")
            if kind not in _ARTIFACT_KINDS:
                row["kind"] = "link"
            seen.add(aid)
            deduped.append(row)
        return deduped[:8]

    def attach_artifacts(self, result: Any) -> Any:
        if result.artifacts:
            return result
        artifacts = self.build_artifacts(result)
        if not artifacts:
            return result
        return replace(result, artifacts=artifacts)


_service: ArtifactRegistryService | None = None


def get_artifact_registry_service() -> ArtifactRegistryService:
    global _service
    if _service is None:
        _service = ArtifactRegistryService()
    return _service


def serialize_execution_result(result: Any) -> dict[str, Any]:
    """Serialize execution result with unified artifact cards attached."""
    enriched = get_artifact_registry_service().attach_artifacts(result)
    payload = dict(enriched.__dict__)
    if enriched.structured is not None and "artifacts" not in (enriched.structured or {}):
        payload["structured"] = {**enriched.structured, "artifacts": enriched.artifacts or []}
    return payload
