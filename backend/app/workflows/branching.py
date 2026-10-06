"""Branch routing for IF / Switch / Decision workflow nodes.

A leaf module (no workflow imports) so the compiler, resolver and graph engine can
all share it:

- ``evaluate_condition`` — a small, safe expression language for path conditions:
  ``and`` / ``or`` / ``not`` (also ``&&`` ``||`` ``!``), parentheses, comparisons
  ``== != > >= < <=`` and ``contains``. Operands can be literals, run parameters
  (``$score`` / ``params.score``), earlier step outputs (``steps.<node>.<path>``)
  or the immediate upstream output (``input.<path>``).
- ``select_rule_branch`` — first path whose condition holds, else the default path.
- ``edge_branches`` — branch labels carried on an edge (``condition.branch``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class ConditionError(ValueError):
    """Raised when a path condition cannot be parsed."""


@dataclass
class ConditionContext:
    parameters: dict[str, Any] = field(default_factory=dict)
    # node id -> output; plus name aliases resolved through ``node_names``.
    step_outputs: dict[str, Any] = field(default_factory=dict)
    node_names: dict[str, str] = field(default_factory=dict)  # alias -> node id
    upstream: dict[str, Any] = field(default_factory=dict)  # pred node id -> output


_TOKEN_RE = re.compile(
    r"""
    \s*(?:
      (?P<template>\{\{.*?\}\})
    | (?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<op>==|!=|>=|<=|&&|\|\||[()<>!])
    | (?P<word>[^\s()<>!=&|"']+)
    )
    """,
    re.VERBOSE,
)

_KEYWORDS = {"and", "or", "not", "contains"}


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    text = text.strip()
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if not match or match.end() == pos:
            raise ConditionError(f"Could not read condition near: {text[pos:pos + 20]!r}")
        pos = match.end()
        kind = match.lastgroup or ""
        value = match.group(kind)
        if kind == "word" and value.lower() in _KEYWORDS:
            tokens.append(("kw", value.lower()))
        elif kind == "op" and value == "&&":
            tokens.append(("kw", "and"))
        elif kind == "op" and value == "||":
            tokens.append(("kw", "or"))
        elif kind == "op" and value == "!":
            tokens.append(("kw", "not"))
        elif kind == "template":
            tokens.append(("word", value[2:-2].strip()))
        else:
            tokens.append((kind, value))
    return tokens


def slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _walk(value: Any, path: list[str]) -> Any:
    current = value
    for part in path:
        if current is None:
            return None
        if isinstance(current, dict):
            if part in current:
                current = current[part]
                continue
            lowered = {str(k).lower(): v for k, v in current.items()}
            current = lowered.get(part.lower())
        elif isinstance(current, list) and part.lstrip("-").isdigit():
            idx = int(part)
            current = current[idx] if -len(current) <= idx < len(current) else None
        else:
            return None
    return current


def _merged_upstream(upstream: dict[str, Any]) -> Any:
    outputs = [v for v in upstream.values() if v is not None]
    if len(outputs) == 1:
        return outputs[0]
    merged: dict[str, Any] = {}
    for out in outputs:
        if isinstance(out, dict):
            merged.update(out)
    return merged


class _Missing:
    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return ""


MISSING = _Missing()


def _resolve_word(word: str, ctx: ConditionContext) -> Any:
    lower = word.lower()
    if lower in {"true", "yes"}:
        return True
    if lower in {"false", "no"}:
        return False
    if lower in {"null", "none", "empty"}:
        return None
    try:
        return float(word) if any(c in word for c in ".eE") else int(word)
    except ValueError:
        pass
    if word.startswith("$"):
        parts = word[1:].split(".")
        return _found(_walk(ctx.parameters, parts))
    if lower.startswith("params.") or lower.startswith("parameters."):
        parts = word.split(".")[1:]
        return _found(_walk(ctx.parameters, parts))
    if lower.startswith("input.") or lower == "input":
        parts = word.split(".")[1:]
        return _found(_walk(_merged_upstream(ctx.upstream), parts))
    if lower.startswith("steps."):
        parts = word.split(".")[1:]
        if not parts:
            raise ConditionError("steps. needs a step name, e.g. steps.lead_scorer.score")
        key = parts[0]
        node_id = (
            key
            if key in ctx.step_outputs
            else ctx.node_names.get(key) or ctx.node_names.get(slug(key))
        )
        if node_id is None:
            return MISSING
        return _found(_walk(ctx.step_outputs.get(node_id), parts[1:]))
    head = word.split(".")[0]
    if head in ctx.parameters:
        return _found(_walk(ctx.parameters, word.split(".")))
    # Unquoted bare word that is not a known reference: a literal (``$status == closed``).
    return word


def _found(value: Any) -> Any:
    return MISSING if value is None else value


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or isinstance(value, _Missing):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _norm_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None or isinstance(value, _Missing):
        return ""
    return str(value).strip().lower()


def _truthy(value: Any) -> bool:
    if isinstance(value, _Missing) or value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return _norm_text(value) not in {"", "false", "0", "no", "none", "null"}


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == "contains":
        if isinstance(left, (list, tuple, set)):
            target = _norm_text(right)
            return any(_norm_text(item) == target for item in left)
        if isinstance(left, dict):
            return _norm_text(right) in {_norm_text(k) for k in left}
        return _norm_text(right) in _norm_text(left)
    if op in {"==", "!="}:
        ln, rn = _as_number(left), _as_number(right)
        if right is None:  # ``x == empty``
            equal = not _truthy(left) if not isinstance(left, (int, float)) else False
        elif ln is not None and rn is not None:
            equal = ln == rn
        else:
            equal = _norm_text(left) == _norm_text(right)
        return equal if op == "==" else not equal
    ln, rn = _as_number(left), _as_number(right)
    if ln is None or rn is None:
        return False  # missing or non-numeric values never satisfy an ordering test
    return {
        ">": ln > rn,
        ">=": ln >= rn,
        "<": ln < rn,
        "<=": ln <= rn,
    }[op]


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]], ctx: ConditionContext) -> None:
        self.tokens = tokens
        self.pos = 0
        self.ctx = ctx

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> tuple[str, str]:
        token = self.peek()
        if token is None:
            raise ConditionError("Condition ended unexpectedly")
        self.pos += 1
        return token

    def parse(self) -> bool:
        value = self.parse_or()
        if self.peek() is not None:
            raise ConditionError(f"Unexpected {self.peek()[1]!r} in condition")
        return value

    def parse_or(self) -> bool:
        value = self.parse_and()
        while self.peek() == ("kw", "or"):
            self.take()
            right = self.parse_and()
            value = value or right
        return value

    def parse_and(self) -> bool:
        value = self.parse_not()
        while self.peek() == ("kw", "and"):
            self.take()
            right = self.parse_not()
            value = value and right
        return value

    def parse_not(self) -> bool:
        if self.peek() == ("kw", "not"):
            self.take()
            return not self.parse_not()
        return self.parse_comparison()

    def parse_comparison(self) -> bool:
        if self.peek() == ("op", "("):
            self.take()
            value = self.parse_or()
            if self.take() != ("op", ")"):
                raise ConditionError("Missing closing parenthesis")
            return value
        left = self.parse_operand()
        token = self.peek()
        if token and token[0] == "op" and token[1] in {"==", "!=", ">", ">=", "<", "<="}:
            self.take()
            return _compare(token[1], left, self.parse_operand())
        if token == ("kw", "contains"):
            self.take()
            return _compare("contains", left, self.parse_operand())
        if token == ("kw", "not") and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1] == ("kw", "contains"):
            self.pos += 2
            return not _compare("contains", left, self.parse_operand())
        return _truthy(left)

    def parse_operand(self) -> Any:
        kind, value = self.take()
        if kind == "string":
            return bytes(value[1:-1], "utf-8").decode("unicode_escape")
        if kind == "word":
            return _resolve_word(value, self.ctx)
        raise ConditionError(f"Expected a value but found {value!r}")


def evaluate_condition(expression: Any, ctx: ConditionContext) -> bool:
    """Evaluate a path condition. Empty conditions are true."""
    text = str(expression or "").strip()
    if not text:
        return True
    return _Parser(_tokenize(text), ctx).parse()


def normalize_paths(raw: Any) -> list[dict[str, Any]]:
    """Normalize builder ``outputPaths`` into ``[{id, label, condition, is_default}]``."""
    paths: list[dict[str, Any]] = []
    if isinstance(raw, dict):  # legacy ``{branch_id: condition}``
        raw = [{"id": k, "label": k, "condition": v} for k, v in raw.items()]
    if not isinstance(raw, list):
        return paths
    for item in raw:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("id") or "").strip()
        if not pid:
            continue
        paths.append(
            {
                "id": pid,
                "label": str(item.get("label") or pid),
                "condition": str(item.get("condition") or "").strip(),
                "is_default": bool(item.get("isDefault") or item.get("is_default")),
            }
        )
    return paths


def select_rule_branch(paths: list[dict[str, Any]], ctx: ConditionContext) -> tuple[str | None, str | None]:
    """Return (matched path id, default path id). Paths without a condition only act as default."""
    default_id: str | None = None
    for path in paths:
        if path.get("is_default"):
            default_id = default_id or path["id"]
            continue
        condition = path.get("condition") or ""
        if condition and evaluate_condition(condition, ctx):
            return path["id"], default_id
    if default_id is None:
        unconditioned = [p["id"] for p in paths if not p.get("condition") and not p.get("is_default")]
        default_id = unconditioned[0] if unconditioned else None
    return None, default_id


def edge_branches(edge: dict[str, Any]) -> list[str]:
    """Branch labels an edge is restricted to (empty = always taken)."""
    labels: list[str] = []
    condition = edge.get("condition")
    if isinstance(condition, dict):
        for key in ("branch", "branches"):
            value = condition.get(key)
            if isinstance(value, str) and value.strip():
                labels.append(value.strip())
            elif isinstance(value, list):
                labels.extend(str(v).strip() for v in value if str(v).strip())
    for key in ("branch", "source_handle", "sourceHandle"):
        value = edge.get(key)
        if isinstance(value, str) and value.strip() and value.strip() not in labels:
            labels.append(value.strip())
    return labels
