"""Install variable templating for marketplace assets (MKT-3.2)."""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from app.marketplace.schemas import InstallVariable

INSTALL_VAR_TOKEN_RE = re.compile(r"\{\{INSTALL_VAR_([A-Z0-9_]+)\}\}")


class VariableResolutionError(Exception):
    """Raised when required install variables are missing or tokens remain unresolved."""

    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or [message]
        super().__init__(message)


def extract_install_var_keys(value: Any) -> set[str]:
    """Collect all `{{INSTALL_VAR_*}}` keys referenced anywhere in JSON-like data."""
    keys: set[str] = set()
    if isinstance(value, str):
        keys.update(match.group(1) for match in INSTALL_VAR_TOKEN_RE.finditer(value))
    elif isinstance(value, dict):
        for nested in value.values():
            keys.update(extract_install_var_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(extract_install_var_keys(item))
    return keys


def _normalize_variables(variables: dict[str, str]) -> dict[str, str]:
    return {str(key).strip().upper(): str(value) for key, value in variables.items()}


def _missing_required_variables(
    declared: list[InstallVariable] | None,
    provided: dict[str, str],
    referenced: set[str],
) -> list[str]:
    missing: list[str] = []
    if declared:
        for variable in declared:
            if not variable.required:
                continue
            if variable.key not in provided and variable.default is None:
                if variable.key in referenced:
                    missing.append(variable.key)
    else:
        for key in sorted(referenced):
            if key not in provided:
                missing.append(key)
    return missing


def _replace_tokens(value: Any, variables: dict[str, str]) -> Any:
    if isinstance(value, str):
        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                return match.group(0)
            return variables[key]

        return INSTALL_VAR_TOKEN_RE.sub(replacer, value)
    if isinstance(value, dict):
        return {key: _replace_tokens(nested, variables) for key, nested in value.items()}
    if isinstance(value, list):
        return [_replace_tokens(item, variables) for item in value]
    return value


def _find_unresolved_tokens(value: Any, path: str = "") -> list[str]:
    unresolved: list[str] = []
    if isinstance(value, str):
        for match in INSTALL_VAR_TOKEN_RE.finditer(value):
            token = match.group(0)
            current = f"{path}: {token}" if path else token
            unresolved.append(current)
    elif isinstance(value, dict):
        for key, nested in value.items():
            current = f"{path}.{key}" if path else str(key)
            unresolved.extend(_find_unresolved_tokens(nested, current))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            current = f"{path}[{index}]" if path else f"[{index}]"
            unresolved.extend(_find_unresolved_tokens(item, current))
    return unresolved


def resolve_variables(
    data: Any,
    variables: dict[str, str],
    *,
    declared: list[InstallVariable] | None = None,
    apply_defaults: bool = True,
) -> Any:
    """
    Deep-replace ``{{INSTALL_VAR_*}}`` tokens in JSON-like data.

    Raises ``VariableResolutionError`` when required variables are missing or tokens remain.
    """
    normalized = _normalize_variables(variables)
    payload = deepcopy(data)
    referenced = extract_install_var_keys(payload)

    if apply_defaults and declared:
        for variable in declared:
            if variable.key not in normalized and variable.default is not None:
                normalized[variable.key] = variable.default

    missing = _missing_required_variables(declared, normalized, referenced)
    if missing:
        raise VariableResolutionError(
            "missing required install variables",
            errors=[f"missing:{key}" for key in missing],
        )

    resolved = _replace_tokens(payload, normalized)
    unresolved = _find_unresolved_tokens(resolved)
    if unresolved:
        raise VariableResolutionError(
            "unresolved install variable tokens",
            errors=unresolved,
        )
    return resolved
