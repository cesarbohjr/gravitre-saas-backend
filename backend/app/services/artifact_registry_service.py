"""Unified artifact registry for chat, connector, and orchestration results (Tier 3)."""
from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import uuid4

_ARTIFACT_KINDS = frozenset(
    {"document", "record", "run", "report", "workspace_file", "link", "hosted_file"}
)


def _artifact_id(kind: str, seed: str) -> str:
    return f"{kind}:{seed}"


def _external_from_result(result: Any) -> str | None:
    external = str(getattr(result, "external_url", None) or "").strip()
    if external.startswith(("http://", "https://")):
        return external
    structured = result.structured if isinstance(getattr(result, "structured", None), dict) else {}
    nested = str(structured.get("external_url") or "").strip()
    if nested.startswith(("http://", "https://")):
        return nested
    return None


class ArtifactRegistryService:
    """Build and attach artifact cards from execution results."""

    def build_artifacts(self, result: Any) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        structured = dict(result.structured or {})
        external_url = _external_from_result(result)
        primary_url = str(result.result_url or "").strip() or None
        # Never promote raw vendor http links as the only artifact when we have a Gravitre home.
        if primary_url and primary_url.startswith(("http://", "https://")) and not external_url:
            external_url = primary_url
            primary_url = None

        run_id = str(structured.get("runId") or "")
        if result.entity_type in {"run", "workflow_run"} or run_id:
            run_id = run_id or str(result.entity_id or "")
            run_href = primary_url or (f"/runs/{run_id}" if run_id else None)
            artifacts.append(
                {
                    "artifact_id": _artifact_id("run", run_id or uuid4().hex),
                    "kind": "run",
                    "title": result.title or result.task_label or "Workflow run",
                    "preview": (result.body or "")[:240] or None,
                    "result_url": run_href,
                    "source": "workflow",
                    "metadata": {
                        "runId": run_id,
                        "workflowId": structured.get("workflowId"),
                        "conversationId": structured.get("conversationId"),
                        "external_url": external_url,
                        "goal": structured.get("goal"),
                    },
                }
            )
        elif primary_url:
            artifacts.append(
                {
                    "artifact_id": _artifact_id("link", result.entity_id or primary_url),
                    "kind": "link",
                    "title": result.task_label or result.title or "Open result",
                    "preview": (result.body or "")[:240] or None,
                    "result_url": primary_url,
                    "source": result.entity_type or "execution",
                    "integration": result.integration,
                    "metadata": {"external_url": external_url} if external_url else {},
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
                    "metadata": {
                        "wordCount": structured.get("wordCount"),
                        "previewHtml": structured.get("previewHtml") or structured.get("preview_html"),
                        "code": structured.get("code") or content,
                        "previewFormat": structured.get("previewFormat") or "markdown",
                    },
                }
            )

        hosted_files = structured.get("hostedFiles") or structured.get("hosted_files") or []
        if isinstance(hosted_files, list):
            for row in hosted_files[:8]:
                if not isinstance(row, dict):
                    continue
                filename = str(row.get("filename") or row.get("name") or "file")
                download = str(row.get("download_url") or row.get("downloadUrl") or "").strip() or None
                artifacts.append(
                    {
                        "artifact_id": _artifact_id(
                            "hosted_file",
                            str(row.get("id") or filename),
                        ),
                        "kind": "hosted_file",
                        "title": filename,
                        "preview": f"{row.get('mime_type') or 'file'} · {row.get('byte_size') or 0} bytes",
                        "mime_type": row.get("mime_type") or row.get("mimeType"),
                        "result_url": download,
                        "source": "chat_hosted_file",
                        "metadata": {
                            "role": row.get("role"),
                            "byteSize": row.get("byte_size") or row.get("byteSize"),
                            "durable": row.get("durable"),
                            "previewHtml": structured.get("previewHtml") or structured.get("preview_html"),
                            "code": structured.get("code"),
                            "previewFormat": structured.get("previewFormat")
                            or structured.get("preview_format"),
                        },
                    }
                )

        if result.entity_type == "connector" and result.success:
            artifacts.append(
                {
                    "artifact_id": _artifact_id("record", result.entity_id or result.integration or "connector"),
                    "kind": "record",
                    "title": result.task_label or result.title or "Connector result",
                    "preview": (result.body or "")[:240] or None,
                    "result_url": primary_url,
                    "source": "connector",
                    "integration": result.integration,
                    "metadata": {"external_url": external_url} if external_url else {},
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
