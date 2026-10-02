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
    "capability_package",
    "play",
    "dataset_pack",
    "dashboard_pack",
    "outcome_pack",
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
    requirement_note: str = Field(default="", alias="requirementNote")

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


class OutcomeKpiConfig(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    unit: str = Field(default="count", max_length=40)
    direction: Literal["increase", "decrease", "maintain"] = "increase"
    target: float | int | str | None = None
    source: str = Field(default="", max_length=160)


class OutcomeContractConfig(BaseModel):
    problem: str = Field(min_length=1, max_length=800)
    target_outcome: str = Field(min_length=1, max_length=800)
    baseline_metric: str | None = Field(default=None, max_length=160)
    success_criteria: list[str] = Field(min_length=1)
    outcome_events: list[str] = Field(min_length=1)
    kpis: list[OutcomeKpiConfig] = Field(min_length=1)
    verification_required: bool = True


class PlayAssetConfig(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1200)
    trigger: dict[str, Any] = Field(default_factory=dict)
    workflow_steps: list[dict[str, Any]] = Field(min_length=1)
    outcome_events: list[str] = Field(min_length=1)
    kpi_keys: list[str] = Field(min_length=1)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    verification: dict[str, Any] = Field(default_factory=dict)
    runtime_inputs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_play_workflow(self) -> "PlayAssetConfig":
        try:
            validate_definition({
                "schema_version": SCHEMA_VERSION,
                "steps": self.workflow_steps,
            })
        except WorkflowValidationError as exc:
            raise ValueError(exc.message) from exc
        return self


class DatasetEntityConfig(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=160)
    primary_key: str = Field(default="id", max_length=120)
    fields: list[str] = Field(default_factory=list)


class DatasetMetricConfig(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    formula: str = Field(min_length=1, max_length=1000)
    unit: str = Field(default="count", max_length=40)


class DatasetPackAssetConfig(BaseModel):
    entities: list[DatasetEntityConfig] = Field(min_length=1)
    metrics: list[DatasetMetricConfig] = Field(default_factory=list)


class DashboardMetricConfig(BaseModel):
    kpi_key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=160)
    visualization: Literal["metric", "trend", "bar", "table", "progress"] = "metric"
    description: str = Field(default="", max_length=500)


class DashboardPackAssetConfig(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    metrics: list[DashboardMetricConfig] = Field(min_length=1)
    refresh_mode: Literal["event", "scheduled", "manual"] = "event"


class OutcomeRuntimeProfileConfig(BaseModel):
    provider: str = Field(min_length=1, max_length=120)
    status: Literal["implementation", "tested", "production_verified"] = "implementation"
    actions: list[str] = Field(min_length=1)


class OutcomePackAssetConfig(BaseModel):
    marketplace_version: Literal["3.0"] = "3.0"
    outcome_contract: OutcomeContractConfig
    agents: list[AgentAssetConfig] = Field(min_length=1)
    plays: list[PlayAssetConfig] = Field(min_length=6)
    knowledge: list[KnowledgePackDocument] = Field(default_factory=list)
    dataset: DatasetPackAssetConfig
    dashboard: DashboardPackAssetConfig
    skills: list[str] = Field(default_factory=list)
    skill_requirements: list[str] = Field(default_factory=list)
    skill_bindings: dict[str, str] = Field(default_factory=dict)
    runtime_profiles: list[OutcomeRuntimeProfileConfig] = Field(default_factory=list)
    connector_alternatives: list[list[str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_outcome_pack(self) -> "OutcomePackAssetConfig":
        declared_kpis = {item.key for item in self.outcome_contract.kpis}
        dashboard_kpis = {item.kpi_key for item in self.dashboard.metrics}
        if not dashboard_kpis.issubset(declared_kpis):
            missing = sorted(dashboard_kpis - declared_kpis)
            raise ValueError(f"dashboard references undeclared KPI keys: {', '.join(missing)}")
        missing_dashboard_kpis = sorted(declared_kpis - dashboard_kpis)
        if missing_dashboard_kpis:
            raise ValueError(
                f"every outcome KPI must be represented on the dashboard: {', '.join(missing_dashboard_kpis)}"
            )
        play_keys = [play.key for play in self.plays]
        if len(play_keys) != len(set(play_keys)):
            raise ValueError("outcome packs must not contain duplicate Play keys")
        declared_runtime_actions = {
            action
            for profile in self.runtime_profiles
            for action in profile.actions
        }
        undeclared_skill_bindings = sorted(
            set(self.skill_bindings) - set(self.skill_requirements)
        )
        if undeclared_skill_bindings:
            raise ValueError(
                "skill bindings reference undeclared requirements: "
                + ", ".join(undeclared_skill_bindings)
            )
        if any(not str(package_id).strip() for package_id in self.skill_bindings.values()):
            raise ValueError("skill bindings require non-empty package ids")
        for play in self.plays:
            missing = sorted(set(play.kpi_keys) - declared_kpis)
            if missing:
                raise ValueError(
                    f"play {play.key} references undeclared KPI keys: {', '.join(missing)}"
                )
            workflow_actions = {
                str((step.get("config") or {}).get("action") or "").strip()
                for step in play.workflow_steps
                if step.get("type") == "invoke_tool"
                and isinstance(step.get("config"), dict)
                and str((step.get("config") or {}).get("action") or "").strip()
            }
            undeclared_actions = sorted(workflow_actions - declared_runtime_actions)
            if undeclared_actions:
                raise ValueError(
                    f"play {play.key} uses actions missing from runtime profiles: {', '.join(undeclared_actions)}"
                )
        return self


class ConnectorConfigAssetConfig(BaseModel):
    connector_type: str = Field(min_length=1)
    label: str = ""
    required: bool = True
    connect_path: str = "/connectors"


class CapabilityPackageResource(BaseModel):
    path: str = Field(min_length=1)
    kind: Literal["reference", "script", "asset"]
    content: str | None = None
    executable: bool = False

    @model_validator(mode="after")
    def script_content_must_remain_inert(self) -> "CapabilityPackageResource":
        if self.executable or self.kind == "script":
            if self.content not in (None, ""):
                raise ValueError("executable capability resources must not embed script content")
        return self


class CapabilityPackageAssetConfig(BaseModel):
    # Every Marketplace capability originates from a vetted installed package.
    source_package_id: str | None = Field(default=None, min_length=1)
    provenance_mode: Literal["git_pinned", "trusted_signature"] | None = None

    # Git provenance is required for git_pinned assets and omitted for trusted
    # signed snapshots.
    repository_url: str | None = None
    commit_sha: str | None = None
    package_path: str = ""
    content_digest: str = Field(min_length=71, max_length=71)
    snapshot_digest: str = Field(min_length=71, max_length=71)

    # Inert package snapshot for review/browse. Executable source contents are
    # intentionally forbidden by CapabilityPackageResource.
    manifest: dict[str, Any] = Field(default_factory=dict)
    resources: list[CapabilityPackageResource] = Field(default_factory=list)

    package_format: str = Field(min_length=1)
    license: str | None = None
    license_policy: str = "review"
    risk_level: str = "moderate"
    signature_status: str = "unsigned"
    publisher_name: str | None = None
    publisher_trust_scope: Literal["none", "organization", "marketplace_verified"] = "none"
    marketplace_publisher_id: str | None = None
    security_scan: dict[str, Any] = Field(default_factory=dict)

    @field_validator("repository_url")
    @classmethod
    def validate_repository_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        from app.capabilities.provenance import normalize_github_repository_url

        return normalize_github_repository_url(value)

    @field_validator("commit_sha")
    @classmethod
    def validate_commit_sha(cls, value: str | None) -> str | None:
        if value is None:
            return None
        commit = value.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("commit_sha must be an exact 40-character Git commit SHA")
        return commit

    @field_validator("content_digest", "snapshot_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        digest = value.strip().lower()
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise ValueError("digest must be sha256:<64 hex characters>")
        return digest

    @field_validator("package_path")
    @classmethod
    def validate_package_path(cls, value: str) -> str:
        path = value.strip().strip("/")
        if ".." in path.split("/"):
            raise ValueError("package_path must not contain path traversal")
        return path

    @model_validator(mode="after")
    def validate_provenance_and_policy(self) -> "CapabilityPackageAssetConfig":
        has_repo = bool(self.repository_url)
        has_commit = bool(self.commit_sha)
        if has_repo != has_commit:
            raise ValueError("Git provenance must include both repository_url and commit_sha")

        effective_mode = self.provenance_mode or (
            "git_pinned" if has_repo and has_commit else None
        )
        if effective_mode == "git_pinned":
            if not has_repo or not has_commit:
                raise ValueError("git_pinned capability packages require exact Git provenance")
        elif effective_mode == "trusted_signature":
            if self.signature_status != "verified":
                raise ValueError("trusted_signature capability packages require a verified signature")
            if self.publisher_trust_scope not in {"organization", "marketplace_verified"}:
                raise ValueError("trusted_signature capability packages require current publisher trust")
        else:
            raise ValueError("capability package provenance is required")

        # Legacy Git-pinned Marketplace assets may predate source_package_id and
        # provenance_mode. They remain readable/installable, but the publish
        # workflow requires a live source package before any new publication.
        if not self.source_package_id and effective_mode != "git_pinned":
            raise ValueError("trusted signed capability packages require source_package_id")

        if not self.manifest and not self.resources:
            raise ValueError("capability Marketplace assets require an inert package snapshot")
        if self.license_policy == "block" or self.risk_level == "blocked":
            raise ValueError("blocked capability packages cannot be published")
        if bool((self.security_scan or {}).get("blocked")):
            raise ValueError("capability package security scan is blocked")
        return self


class IntelligencePackAssignmentConfig(BaseModel):
    source_type: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    department: str = Field(min_length=1)
    subdomain: str | None = None
    confidence_weight: float = 1.0
    reference_summary: str = ""
    external_url: str | None = None


class IntelligencePackAssetConfig(BaseModel):
    department: str = Field(min_length=1)
    default_subdomain: str | None = None
    assignments: list[IntelligencePackAssignmentConfig] = Field(min_length=1)


ASSET_CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "ai_agent": AgentAssetConfig,
    "workflow": WorkflowAssetConfig,
    "knowledge_pack": KnowledgePackAssetConfig,
    "department_pack": DepartmentPackAssetConfig,
    "connector_config": ConnectorConfigAssetConfig,
    "capability_package": CapabilityPackageAssetConfig,
    "intelligence_pack": IntelligencePackAssetConfig,
    "play": PlayAssetConfig,
    "dataset_pack": DatasetPackAssetConfig,
    "dashboard_pack": DashboardPackAssetConfig,
    "outcome_pack": OutcomePackAssetConfig,
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


def assert_no_forbidden_secrets(value: Any, *, field_label: str) -> None:
    """Raise when ``value`` contains credential-like keys anywhere in the tree."""
    secret_paths = find_forbidden_secret_paths(value)
    if secret_paths:
        raise MarketplaceValidationError(
            f"{field_label} must not contain secret or credential fields",
            errors=[f"forbidden_secret:{path}" for path in secret_paths],
        )


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
    """Validate asset ``config`` JSONB for draft save or publish transition."""
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
    assert_no_forbidden_secrets(config, field_label="config")
    model_cls = ASSET_CONFIG_MODELS[asset_type]
    try:
        parsed = model_cls.model_validate(config)
    except ValidationError as exc:
        raise MarketplaceValidationError(
            f"invalid {asset_type} config",
            errors=_format_pydantic_errors(exc),
        ) from exc

    if publish:
        _assert_publish_ready(asset_type, parsed)

    return parsed


def _assert_publish_ready(asset_type: str, parsed: BaseModel) -> None:
    """Stricter validation gate for submit/approve transitions."""
    if asset_type == "ai_agent":
        agent = parsed  # type: ignore[assignment]
        if not agent.purpose.strip():  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "ai_agent config requires a non-empty purpose for publish",
                errors=["purpose_required"],
            )
    elif asset_type == "workflow":
        workflow = parsed  # type: ignore[assignment]
        if not workflow.description.strip():  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "workflow config requires a description for publish",
                errors=["description_required"],
            )
    elif asset_type == "knowledge_pack":
        pack = parsed  # type: ignore[assignment]
        if not pack.documents:  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "knowledge_pack requires at least one document for publish",
                errors=["documents_required"],
            )
    elif asset_type == "department_pack":
        pack = parsed  # type: ignore[assignment]
        if not pack.agents:  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "department_pack requires at least one agent for publish",
                errors=["agents_required"],
            )
        if not pack.workflow_steps:  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "department_pack requires workflow_steps for publish",
                errors=["workflow_steps_required"],
            )
    elif asset_type == "play":
        play = parsed  # type: ignore[assignment]
        if not play.outcome_events:  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "play requires at least one outcome event for publish",
                errors=["outcome_events_required"],
            )
    elif asset_type == "dataset_pack":
        dataset = parsed  # type: ignore[assignment]
        if not dataset.entities:  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "dataset_pack requires at least one entity for publish",
                errors=["entities_required"],
            )
    elif asset_type == "dashboard_pack":
        dashboard = parsed  # type: ignore[assignment]
        if not dashboard.metrics:  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "dashboard_pack requires at least one metric for publish",
                errors=["metrics_required"],
            )
    elif asset_type == "outcome_pack":
        pack = parsed  # type: ignore[assignment]
        if len(pack.plays) < 6:  # type: ignore[attr-defined]
            raise MarketplaceValidationError(
                "Marketplace 3.0 outcome packs require at least six meaningful plays",
                errors=["minimum_six_plays_required"],
            )


def validate_asset_payload(
    *,
    asset_type: str,
    config: dict[str, Any],
    install_variables: list[Any] | None = None,
    required_connectors: list[Any] | None = None,
    publish: bool = False,
    enforce_bindings: bool | None = None,
) -> dict[str, Any]:
    """Validate config plus top-level marketplace asset metadata fields.

    Binding checks hard-fail when ``enforce_bindings`` is true (defaults to
    ``publish``). Seed/catalog validation may still pass ``enforce_bindings=False``
    for structural-only checks; install continues to gate via install-ready.
    """
    from app.workflows.binding_validation import assert_bindings_valid
    from app.workflows.constants import SCHEMA_VERSION as WF_SCHEMA_VERSION

    assert_no_forbidden_secrets(install_variables, field_label="install_variables")
    assert_no_forbidden_secrets(required_connectors, field_label="required_connectors")
    parsed_config = parse_asset_config(asset_type, config, publish=publish)
    parsed_variables = validate_install_variables(install_variables)
    parsed_connectors = validate_required_connectors(required_connectors)

    declared = {str(item.key) for item in parsed_variables if getattr(item, "key", None)}
    steps: list[dict[str, Any]] | None = None
    schema_version = WF_SCHEMA_VERSION
    dumped = parsed_config.model_dump(mode="json")
    if asset_type == "workflow" and isinstance(dumped.get("steps"), list):
        steps = dumped["steps"]
        schema_version = str(dumped.get("schema_version") or WF_SCHEMA_VERSION)
    elif asset_type == "department_pack" and isinstance(dumped.get("workflow_steps"), list):
        steps = dumped["workflow_steps"]
    elif asset_type == "play" and isinstance(dumped.get("workflow_steps"), list):
        steps = dumped["workflow_steps"]
        declared.update(
            str(value).strip()
            for value in (dumped.get("runtime_inputs") or [])
            if str(value).strip()
        )
    should_enforce = publish if enforce_bindings is None else enforce_bindings
    if steps and should_enforce:
        try:
            assert_bindings_valid(
                {"schema_version": schema_version, "steps": steps},
                declared_parameters=declared,
            )
        except WorkflowValidationError as exc:
            raise MarketplaceValidationError(
                exc.message,
                errors=list(exc.errors or []),
            ) from exc

    return {
        "config": dumped,
        "install_variables": [item.model_dump(mode="json") for item in parsed_variables],
        "required_connectors": [item.model_dump(mode="json", by_alias=True) for item in parsed_connectors],
    }
