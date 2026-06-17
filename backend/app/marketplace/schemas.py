"""Marketplace asset config schemas and validation gates (MKT-3.1, MKT-9.5)."""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.workflows.constants import SCHEMA_VERSION
from app.workflows.schema import WorkflowValidationError, validate_definition

AssetType = Literal[
    "ai_agent",
    "workflow",
    "knowledge_pack",
    "department_pack",
    "connector_config",
]

FORBIDDEN_SECRET_KEYS = frozenset({
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "client_secret",
    "password",
    "secret",
    "oauth_token",
    "private_key",
    "bearer_token",
    "authorization",
})

FORBIDDEN_SECRET_SUFFIXES = ("_token", "_secret", "_password", "_api_key")


class MarketplaceValidationError(Exception):
    """Raised when marketplace asset config or metadata fails validation."""

    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or [message]
        super().__init__(message)


class InstallVariable(BaseModel):
    """User-supplied value required at install time (`{{INSTALL_VAR_KEY}}` tokens)."""

    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=200)
    description: str = ""
    required: bool = True
    default: str | None = None

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9_]+", normalized):
            raise ValueError("key must be uppercase alphanumeric with underscores")
        return normalized


class RequiredConnectorRef(BaseModel):
    connector_type: str = Field(min_length=1, alias="connectorType")
    label: str = ""
    required: bool = True
    connect_path: str = Field(default="/connectors", alias="connectPath")

    model_config = {"populate_by_name": True}


class AgentAssetConfig(BaseModel):
    seed_label: str | None = None
    name: str = Field(min_length=1)
    purpose: str = ""
    role: str = ""
    department: str = ""
    model: str = "gpt-4.1"
    capabilities: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    persona_key: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class KnowledgePackDocument(BaseModel):
    seed_label: str | None = None
    title: str = Field(min_length=1)
    type: str = "manual"
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgePackAssetConfig(BaseModel):
    documents: list[KnowledgePackDocument] = Field(min_length=1)


class WorkflowAssetConfig(BaseModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    name: str = Field(min_length=1)
    description: str = ""
    steps: list[dict[str, Any]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_workflow_definition(self) -> WorkflowAssetConfig:
        try:
            validate_definition({
                "schema_version": self.schema_version,
                "steps": self.steps,
            })
        except WorkflowValidationError as exc:
            raise ValueError(exc.message) from exc
        return self


class DepartmentPackAssetConfig(BaseModel):
    workflow_name: str = Field(min_length=1)
    workflow_description: str = ""
    agents: list[AgentAssetConfig] = Field(min_length=1)
    rag_sources: list[KnowledgePackDocument] = Field(default_factory=list)
    workflow_steps: list[dict[str, Any]] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_embedded_workflow(self) -> DepartmentPackAssetConfig:
        try:
            validate_definition({
                "schema_version": SCHEMA_VERSION,
                "steps": self.workflow_steps,
            })
        except WorkflowValidationError as exc:
            raise ValueError(exc.message) from exc
        return self


class ConnectorConfigAssetConfig(BaseModel):
    connector_type: str = Field(min_length=1)
    label: str = ""
    required: bool = True
    connect_path: str = "/connectors"


ASSET_CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "ai_agent": AgentAssetConfig,
    "workflow": WorkflowAssetConfig,
    "knowledge_pack": KnowledgePackAssetConfig,
    "department_pack": DepartmentPackAssetConfig,
    "connector_config": ConnectorConfigAssetConfig,
}


def find_forbidden_secret_paths(value: Any, path: str = "") -> list[str]:
    """Return dotted paths of keys that look like embedded secrets (MKT-9.5)."""
    errors: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_lower = str(key).lower()
            current = f"{path}.{key}" if path else str(key)
            if key_lower in FORBIDDEN_SECRET_KEYS or any(
                key_lower.endswith(suffix) for suffix in FORBIDDEN_SECRET_SUFFIXES
            ):
                errors.append(current)
            errors.extend(find_forbidden_secret_paths(nested, current))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(find_forbidden_secret_paths(item, f"{path}[{index}]"))
    return errors


def _format_pydantic_errors(exc: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
        for err in exc.errors()
    ]


def validate_install_variables(raw: list[Any] | None) -> list[InstallVariable]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise MarketplaceValidationError(
            "install_variables must be an array",
            errors=["install_variables_invalid"],
        )
    parsed: list[InstallVariable] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        try:
            variable = InstallVariable.model_validate(item)
        except ValidationError as exc:
            raise MarketplaceValidationError(
                f"install_variables[{index}] is invalid",
                errors=_format_pydantic_errors(exc),
            ) from exc
        if variable.key in seen:
            raise MarketplaceValidationError(
                f"duplicate install variable key: {variable.key}",
                errors=["install_variables_duplicate_key"],
            )
        seen.add(variable.key)
        parsed.append(variable)
    return parsed


def validate_required_connectors(raw: list[Any] | None) -> list[RequiredConnectorRef]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise MarketplaceValidationError(
            "required_connectors must be an array",
            errors=["required_connectors_invalid"],
        )
    parsed: list[RequiredConnectorRef] = []
    for index, item in enumerate(raw):
        try:
            parsed.append(RequiredConnectorRef.model_validate(item))
        except ValidationError as exc:
            raise MarketplaceValidationError(
                f"required_connectors[{index}] is invalid",
                errors=_format_pydantic_errors(exc),
            ) from exc
    return parsed


def parse_asset_config(
    asset_type: str,
    config: dict[str, Any],
    *,
    publish: bool = False,
) -> BaseModel:
    """
    Validate asset `config` JSONB for draft save or publish transition.

    ``publish=True`` re-validates with the same rules today; reserved for stricter gates.
    """
    _ = publish
    if asset_type not in ASSET_CONFIG_MODELS:
        raise MarketplaceValidationError(
            f"unsupported asset_type: {asset_type!r}",
            errors=["unsupported_asset_type"],
        )
    if not isinstance(config, dict):
        raise MarketplaceValidationError(
            "config must be an object",
            errors=["config_invalid"],
        )
    secret_paths = find_forbidden_secret_paths(config)
    if secret_paths:
        raise MarketplaceValidationError(
            "config must not contain secret or credential fields",
            errors=[f"forbidden_secret:{path}" for path in secret_paths],
        )
    model_cls = ASSET_CONFIG_MODELS[asset_type]
    try:
        return model_cls.model_validate(config)
    except ValidationError as exc:
        raise MarketplaceValidationError(
            f"invalid {asset_type} config",
            errors=_format_pydantic_errors(exc),
        ) from exc


def validate_asset_payload(
    *,
    asset_type: str,
    config: dict[str, Any],
    install_variables: list[Any] | None = None,
    required_connectors: list[Any] | None = None,
    publish: bool = False,
) -> dict[str, Any]:
    """Validate config plus top-level marketplace asset metadata fields."""
    parsed_config = parse_asset_config(asset_type, config, publish=publish)
    parsed_variables = validate_install_variables(install_variables)
    parsed_connectors = validate_required_connectors(required_connectors)
    return {
        "config": parsed_config.model_dump(mode="json"),
        "install_variables": [item.model_dump(mode="json") for item in parsed_variables],
        "required_connectors": [item.model_dump(mode="json", by_alias=True) for item in parsed_connectors],
    }
