"""Import adapters for portable capability bundles.

A bundle is a mapping of relative path -> UTF-8 text. This is the normalized
input produced by Git/ZIP upload adapters. Binary assets and scripts are not
executed here.
"""
from __future__ import annotations

import io
import json
import stat
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.capabilities.packages import PackageInspection, inspect_package

MAX_FILES = 250
MAX_TEXT_BYTES = 2_000_000
MAX_ZIP_BYTES = 10_000_000
RESOURCE_SUFFIXES = (".md", ".txt", ".json", ".yaml", ".yml")
SCRIPT_SUFFIXES = (".py", ".js", ".ts", ".sh", ".bash", ".ps1")


@dataclass(frozen=True)
class ImportedBundle:
    manifest: dict[str, Any]
    skill_md: str | None
    inspection: PackageInspection
    resources: tuple[dict[str, Any], ...]
    ignored_files: tuple[str, ...]


def _parse_json(text: str, path: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _pick_manifest(files: dict[str, str]) -> tuple[dict[str, Any], str | None]:
    candidates = (
        "gravitre-plugin.json",
        ".codex-plugin/plugin.json",
        ".claude-plugin/plugin.json",
        "plugin.json",
        ".mcp.json",
        "mcp.json",
    )
    lowered = {path.lower(): path for path in files}
    for candidate in candidates:
        path = lowered.get(candidate.lower())
        if path:
            return _parse_json(files[path], path), path
    return {}, None


def import_file_bundle(files: dict[str, str]) -> ImportedBundle:
    if not files:
        raise ValueError("Package bundle is empty")
    if len(files) > MAX_FILES:
        raise ValueError(f"Package bundle exceeds {MAX_FILES} files")

    total = sum(len(str(content).encode("utf-8")) for content in files.values())
    if total > MAX_TEXT_BYTES:
        raise ValueError("Package textual content exceeds size limit")

    normalized: dict[str, str] = {}
    for raw_path, content in files.items():
        path = str(raw_path).strip().replace("\\", "/")
        if not path:
            continue
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or ".." in parsed.parts:
            raise ValueError("Package contains unsafe path traversal")
        normalized[str(parsed)] = str(content)
    manifest, manifest_path = _pick_manifest(normalized)
    skill_path = next(
        (path for path in normalized if path.lower() == "skill.md" or path.lower().endswith("/skill.md")),
        None,
    )
    skill_md = normalized.get(skill_path) if skill_path else None

    # Add format hints without mutating source files.
    if manifest_path == ".codex-plugin/plugin.json":
        manifest = {**manifest, "format": manifest.get("format") or "openai-codex-plugin"}
    elif manifest_path == ".claude-plugin/plugin.json":
        manifest = {**manifest, "format": manifest.get("format") or "claude-plugin"}
    elif manifest_path in {".mcp.json", "mcp.json"}:
        manifest = {"name": manifest.get("name") or "mcp-package", "format": "mcp", "mcpServers": manifest.get("mcpServers") or manifest}

    inspection = inspect_package(manifest, skill_md=skill_md)

    resources: list[dict[str, Any]] = []
    ignored: list[str] = []
    for path, content in normalized.items():
        lower = path.lower()
        if path == manifest_path:
            continue
        if path == skill_path:
            resources.append({"path": path, "kind": "reference", "content": content, "executable": False})
            continue
        if lower.endswith(SCRIPT_SUFFIXES):
            resources.append({"path": path, "kind": "script", "content": None, "executable": True})
            continue
        if lower.endswith(RESOURCE_SUFFIXES):
            resources.append({"path": path, "kind": "reference", "content": content, "executable": False})
        else:
            ignored.append(path)

    return ImportedBundle(
        manifest=manifest,
        skill_md=skill_md,
        inspection=inspection,
        resources=tuple(resources),
        ignored_files=tuple(sorted(ignored)),
    )


def read_zip_bundle(data: bytes) -> dict[str, str]:
    """Extract supported UTF-8 capability files from a ZIP without executing them."""
    if not data:
        raise ValueError("ZIP package is empty")
    if len(data) > MAX_ZIP_BYTES:
        raise ValueError("ZIP package exceeds 10MB upload limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("Invalid ZIP package") from exc

    files: dict[str, str] = {}
    total_text_bytes = 0
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_FILES * 4:
            raise ValueError("ZIP package contains too many entries")
        for info in infos:
            if info.is_dir():
                continue
            raw_path = str(info.filename or "").replace("\\", "/")
            path = PurePosixPath(raw_path)
            if not raw_path or path.is_absolute() or ".." in path.parts:
                raise ValueError("ZIP contains unsafe path traversal")
            mode = (info.external_attr >> 16) & 0xFFFF
            if mode and stat.S_ISLNK(mode):
                raise ValueError("ZIP symbolic links are not allowed")
            if info.file_size > MAX_TEXT_BYTES:
                raise ValueError("ZIP entry exceeds text size limit")

            lower_name = path.name.lower()
            suffix = path.suffix.lower()
            supported = (
                suffix in RESOURCE_SUFFIXES
                or suffix in SCRIPT_SUFFIXES
                or lower_name in {"skill.md", "plugin.json", "gravitre-plugin.json", ".mcp.json", "mcp.json"}
            )
            if not supported:
                continue

            payload = archive.read(info)
            total_text_bytes += len(payload)
            if total_text_bytes > MAX_TEXT_BYTES:
                raise ValueError("ZIP textual content exceeds size limit")
            try:
                text_value = payload.decode("utf-8")
            except UnicodeDecodeError:
                continue
            files[str(path)] = text_value
            if len(files) > MAX_FILES:
                raise ValueError(f"ZIP package exceeds {MAX_FILES} supported text files")

    if not files:
        raise ValueError("ZIP contains no supported capability files")
    return files
