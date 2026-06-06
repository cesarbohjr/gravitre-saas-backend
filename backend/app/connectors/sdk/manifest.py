"""Connector manifest schema validation (STA-70 / T3-015)."""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MANIFEST_VERSION = "1.0"
VENDOR_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
ACTION_ID_RE = re.compile(r"^[a-z][a-z0-9_.]{1,127}$")


class OAuthAuthConfig(BaseModel):
    """OAuth2 connector authentication."""

    type: Literal["oauth2"] = "oauth2"
    authorization_url: str = Field(alias="authorizationUrl")
    token_url: str = Field(alias="tokenUrl")
    scopes: list[str] = Field(default_factory=list)
    refresh_supported: bool = Field(default=True, alias="refreshSupported")

    model_config = {"populate_by_name": True}


class ApiKeyAuthConfig(BaseModel):
    """API key connector authentication."""

    type: Literal["apiKey"] = "apiKey"
    header_name: str = Field(default="Authorization", alias="headerName")
    prefix: str | None = None

    model_config = {"populate_by_name": True}


AuthConfig = OAuthAuthConfig | ApiKeyAuthConfig


class ActionDefinition(BaseModel):
    """Declarative tool action exposed via invoke_tool."""

    id: str
    name: str
    description: str = ""
    scopes: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")
    output_schema: dict[str, Any] = Field(default_factory=dict, alias="outputSchema")
    idempotent: bool = False
    destructive: bool = False

    model_config = {"populate_by_name": True}

    @field_validator("id")
    @classmethod
    def validate_action_id(cls, value: str) -> str:
        if not ACTION_ID_RE.match(value):
            raise ValueError("action id must be lowercase alphanumeric with dots/underscores")
        return value


class TriggerDefinition(BaseModel):
    """Inbound event that can start workflows."""

    id: str
    name: str
    description: str = ""
    event_type: Literal["webhook", "poll", "push"] = Field(default="webhook", alias="eventType")
    scopes: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @field_validator("id")
    @classmethod
    def validate_trigger_id(cls, value: str) -> str:
        if not ACTION_ID_RE.match(value):
            raise ValueError("trigger id must be lowercase alphanumeric with dots/underscores")
        return value


class ConnectorManifest(BaseModel):
    """Partner connector package manifest (manifest.json)."""

    manifest_version: str = Field(alias="manifestVersion")
    id: str
    name: str
    version: str
    vendor: str
    description: str = ""
    auth: OAuthAuthConfig | ApiKeyAuthConfig
    capabilities: list[Literal["actions", "triggers", "sync", "rag"]] = Field(default_factory=list)
    actions: list[ActionDefinition] = Field(default_factory=list)
    triggers: list[TriggerDefinition] = Field(default_factory=list)
    min_platform_version: str | None = Field(default=None, alias="minPlatformVersion")
    homepage_url: str | None = Field(default=None, alias="homepageUrl")
    support_email: str | None = Field(default=None, alias="supportEmail")

    model_config = {"populate_by_name": True}

    @field_validator("manifest_version")
    @classmethod
    def validate_manifest_version(cls, value: str) -> str:
        if value != MANIFEST_VERSION:
            raise ValueError(f"unsupported manifestVersion {value!r}; expected {MANIFEST_VERSION}")
        return value

    @field_validator("vendor")
    @classmethod
    def validate_vendor(cls, value: str) -> str:
        if not VENDOR_SLUG_RE.match(value):
            raise ValueError("vendor must be a lowercase slug (a-z, 0-9, underscore)")
        return value

    @model_validator(mode="after")
    def validate_capabilities(self) -> ConnectorManifest:
        caps = set(self.capabilities)
        if "actions" in caps and not self.actions:
            raise ValueError("capabilities includes actions but no actions are declared")
        if "triggers" in caps and not self.triggers:
            raise ValueError("capabilities includes triggers but no triggers are declared")
        action_ids = [action.id for action in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("duplicate action ids in manifest")
        trigger_ids = [trigger.id for trigger in self.triggers]
        if len(trigger_ids) != len(set(trigger_ids)):
            raise ValueError("duplicate trigger ids in manifest")
        return self

    def action_keys(self) -> list[str]:
        """Canonical invoke_tool action names: {vendor}.{action_id}."""
        return [f"{self.vendor}.{action.id}" for action in self.actions]

    def scopes_for_action(self, action_key: str) -> list[str]:
        """Return declared scopes for a canonical action key."""
        prefix = f"{self.vendor}."
        if not action_key.startswith(prefix):
            return []
        action_id = action_key[len(prefix) :]
        for action in self.actions:
            if action.id == action_id:
                if action.scopes:
                    return list(action.scopes)
                return [f"{self.vendor}:*", action_key]
        return []


def parse_manifest(data: dict[str, Any]) -> ConnectorManifest:
    """Validate and parse a manifest.json document."""
    return ConnectorManifest.model_validate(data)
