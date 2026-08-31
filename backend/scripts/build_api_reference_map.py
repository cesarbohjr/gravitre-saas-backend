"""Derive each catalog action's real vendor endpoint from connector code.

This does NOT guess an endpoint from the action's name. For every action it
resolves the executor that ``invoke_tool`` would really call, then walks the
real call graph (executor -> vendor api helper -> the httpx call site) and
transcribes the method + path literal found at the emission site, recording the
source file and line so every entry carries its own evidence pointer.

Resolution handles the three indirections this codebase actually uses:
closure-captured handlers (``make_phase2_executor``), function-local
``from x import y`` imports, and positional api helpers whose argument order
differs per vendor (bound via the real ``inspect.signature``).

Four provenance classes, which are NOT equally trustworthy:

  dedicated      transcribed from a purpose-written executor's real call site.
  route_table    read from a hand-written method+path table (twilio).
  name_inferred  the generic catalog_http executor computes method+path from the
                 action suffix at import time via _infer_route(). The recorded
                 route is genuinely what the process sends, but nothing has ever
                 checked it against the vendor's real API.
  undetermined   no single endpoint could be transcribed. Reported, never guessed.

Writes docs/delivery/api-reference-map.json.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.stdout.reconfigure(encoding="utf-8")

from app.connectors.action_catalog.api_reference_overrides import REVIEWED, manual_reference
from app.connectors.action_catalog.api_reference_review import (
    REVIEWED as AMBIGUITY_REVIEWED,
    ambiguity_verdict,
)
from app.connectors.action_catalog.registry import get_vendor_catalog
from app.connectors.action_catalog.vendor_contracts import vendor_contract
from app.connectors.action_catalog.tool_aliases import registry_keys_for_catalog_tool
from app.connectors.catalog_http.executor import _infer_route
from app.connectors.catalog_http.profiles import VENDOR_HTTP_PROFILES
from app.services.tool_service import _TOOL_REGISTRY

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
CLIENT_OBJECTS = {"client", "httpx", "session", "_client", "http_client"}
CLIENT_VERBS = {"get", "post", "put", "patch", "delete", "head", "options", "request"}
PATH_ARG_NAMES = ("path", "url", "endpoint", "uri", "route", "resource")

# Never recurse into these: auth/session/rate-limit/notification/error plumbing
# makes its own HTTP calls (token refresh, Supabase writes) that are not the
# action's vendor endpoint.
SKIP_CALLEE_RE = re.compile(
    r"(^_?session$|token|secret|_connector$|connector_and|resolve_connector|ensure_.*session"
    r"|rate_limit|notification|notify|audit|_handle_error|_handle_.*_error|^emit|_emit"
    r"|_payload_from_params|_with_result_url|^_stamp_|_search_params|logger|^log_|^record_"
    r"|track_usage|settings|verify_.*_credentials|verify_.*_api_key|_format_.*_error"
    r"|^authenticate$|_authenticate$)",
    re.IGNORECASE,
)

ACTION_VARS = {"action", "tool", "tool_key", "suffix", "name", "op", "operation"}

BASE_CONST_PREFERENCE = (
    "API_BASE",
    "API_BASE_URL",
    "BASE_URL",
    "BASE",
    "API_URL",
    "API_ROOT",
    "GRAPH_BASE",
    "GRAPHQL_URL",
    "ENDPOINT",
)

VERB_EXPECTED_METHOD = {
    "get": {"GET"},
    "list": {"GET"},
    "create": {"POST"},
    "add": {"POST"},
    "send": {"POST"},
    "update": {"PUT", "PATCH", "POST"},
    "modify": {"PUT", "PATCH", "POST"},
    "delete": {"DELETE"},
    "remove": {"DELETE"},
    "search": {"POST", "GET"},
}


@dataclass
class Endpoint:
    method: str
    path: str
    base: str | None
    base_const: str | None
    source: str
    style: str = "rest"
    graphql_op: str | None = None
    operation: str | None = None

    def key(self) -> tuple:
        return (self.method, self.path, self.style, self.graphql_op, self.operation)

    def reference(self) -> str:
        if self.style == "graphql":
            op = f" ({self.graphql_op})" if self.graphql_op else ""
            return f"POST {self.base or 'graphql'}{op}"
        if self.operation:
            return f"{self.method} {self.path} ({self.operation})"
        return f"{self.method} {self.path}"


@dataclass
class Walk:
    action: str
    endpoints: list[Endpoint] = field(default_factory=list)
    visited: set[tuple[str, str]] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------- catalog side


def catalog_specs() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for vendor_spec in get_vendor_catalog().values():
        for spec in vendor_spec.all_actions():
            tool_key = spec.id
            if "." not in tool_key or tool_key.split(".", 1)[0] != vendor_spec.vendor:
                tool_key = f"{vendor_spec.vendor}.{spec.id}"
            out[tool_key] = spec
    return dict(sorted(out.items()))


def resolve_executor(action: str):
    fn = _TOOL_REGISTRY.get(action)
    if fn is not None:
        return action, fn
    for key in sorted(registry_keys_for_catalog_tool(action)):
        fn = _TOOL_REGISTRY.get(key)
        if fn is not None:
            return key, fn
    return None, None


def rel(path: str | None) -> str:
    if not path:
        return ""
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except Exception:
        return Path(path).name


# ------------------------------------------------------------- name resolution


def closure_map(fn: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    code = getattr(fn, "__code__", None)
    cells = getattr(fn, "__closure__", None)
    if code is None or not cells:
        return out
    for name, cell in zip(code.co_freevars, cells):
        try:
            out[name] = cell.cell_contents
        except ValueError:
            continue
    return out


def local_imports(tree: ast.AST) -> dict[str, Any]:
    """Resolve function-local `from x import y` / `import x` bindings."""
    out: dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            try:
                mod = importlib.import_module(node.module)
            except Exception:
                continue
            for alias in node.names:
                obj = getattr(mod, alias.name, None)
                if obj is not None:
                    out[alias.asname or alias.name] = obj
        elif isinstance(node, ast.Import):
            for alias in node.names:
                try:
                    mod = importlib.import_module(alias.name)
                except Exception:
                    continue
                out[(alias.asname or alias.name).split(".")[0]] = mod
    return out


# ------------------------------------------------------------ string rendering


def _simplify_expr(expr: str) -> str:
    """Reduce an f-string placeholder expression to the parameter it carries."""
    expr = expr.strip()
    # Unwrap encoding/coercion wrappers: quote(str(worker_id), safe='') -> worker_id
    for _ in range(4):
        m = re.match(r"^(?:str|quote|quote_plus|urlencode|int|repr)\(\s*(.+?)\s*(?:,[^)]*)?\)$", expr)
        if not m:
            break
        expr = m.group(1).strip()
    # text.replace(...) / value.strip() -> text
    expr = re.sub(r"^([\w]+)\s*\.\s*(replace|strip|lstrip|rstrip|lower|upper)\(.*\)$", r"\1", expr)
    m = re.search(r"""\[\s*['"]([\w]+)['"]\s*\]\s*$""", expr)
    if m:
        return m.group(1)
    m = re.search(r"""\.get\(\s*['"]([\w]+)['"]""", expr)
    if m:
        return m.group(1)
    m = re.search(r"([\w]+)\s*$", expr)
    return m.group(1) if m else expr


def render_str(
    node: ast.AST | None,
    locals_map: dict[str, ast.AST] | None = None,
    depth: int = 0,
    consts: dict[str, str] | None = None,
) -> str | None:
    if node is None or depth > 3:
        return None
    locals_map = locals_map or {}
    consts = consts or {}
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                inner = value.value
                if isinstance(inner, ast.Name):
                    # A module-level string constant is a real literal path part.
                    if inner.id in consts:
                        parts.append(consts[inner.id])
                        continue
                    if inner.id in locals_map:
                        sub = render_str(locals_map[inner.id], locals_map, depth + 1, consts)
                        if sub:
                            parts.append(sub)
                            continue
                parts.append("{" + _simplify_expr(ast.unparse(inner)) + "}")
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = render_str(node.left, locals_map, depth + 1, consts)
        right = render_str(node.right, locals_map, depth + 1, consts)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.Name):
        if node.id in consts:
            return consts[node.id]
        if node.id in locals_map:
            return render_str(locals_map[node.id], locals_map, depth + 1, consts)
        return None
    return None


def collect_locals(tree: ast.AST) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and node.value is not None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                out[node.target.id] = node.value
    return out


def _is_client_ctor(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in {"Client", "AsyncClient"}
    if isinstance(func, ast.Name):
        return func.id in {"Client", "AsyncClient"}
    return False


def http_client_names(tree: ast.AST) -> set[str]:
    """Names actually bound to an httpx client inside this function.

    Detecting the receiver this way (rather than by a guessed variable name)
    is what stops ``payload.get("createdAt")`` being transcribed as an
    endpoint, while still catching ``with httpx.Client() as c: c.get(...)``.
    """
    names: set[str] = set(CLIENT_OBJECTS)
    for node in ast.walk(tree):
        if isinstance(node, ast.With) or isinstance(node, getattr(ast, "AsyncWith", ast.With)):
            for item in getattr(node, "items", []):
                if _is_client_ctor(item.context_expr) and isinstance(item.optional_vars, ast.Name):
                    names.add(item.optional_vars.id)
        elif isinstance(node, ast.Assign) and _is_client_ctor(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def is_http_client(obj: ast.AST, client_names: set[str]) -> bool:
    """True only for a real HTTP client receiver — not any object with .get()."""
    if isinstance(obj, ast.Name):
        return obj.id in client_names
    if isinstance(obj, ast.Attribute):
        return obj.attr in client_names or (
            isinstance(obj.value, ast.Name) and obj.value.id in {"httpx", "requests"}
        )
    return _is_client_ctor(obj)


def looks_like_path(path: str) -> bool:
    """Reject strings that are dict keys or field names, not request paths."""
    if not path:
        return False
    if path.startswith("/") or path.startswith("http"):
        return True
    if "/" in path:
        return True
    # Clio/Shopify style relative resources, e.g. "contacts.json"
    return bool(re.match(r"^[\w-]+\.(json|xml)$", path))


def split_base(url: str) -> tuple[str | None, str]:
    m = re.match(r"^\{([\w]+)\}(.*)$", url)
    if m and re.search(r"(base|url|root|endpoint|host|api)", m.group(1), re.IGNORECASE):
        return m.group(1), m.group(2) or "/"
    if url.startswith("http"):
        m2 = re.match(r"^(https?://[^/]+)(/.*)?$", url)
        if m2:
            return m2.group(1), m2.group(2) or "/"
    return None, url


def graphql_operation(text: str) -> str | None:
    body = " ".join(text.split())
    m = re.match(r"^(query|mutation|subscription)\b", body)
    kind = m.group(1) if m else "query"
    inner = re.search(r"\{\s*([A-Za-z_][\w]*)\s*[({]", body)
    if inner:
        return f"{kind} {inner.group(1)}"
    return kind if m else None


def module_base(fn: Any) -> tuple[str | None, str | None]:
    g = getattr(fn, "__globals__", {}) or {}
    for name in BASE_CONST_PREFERENCE:
        value = g.get(name)
        if isinstance(value, str) and value.startswith("http"):
            return name, value
    candidates = [
        (n, v)
        for n, v in g.items()
        if isinstance(v, str)
        and v.startswith("http")
        and n.isupper()
        and re.search(r"(BASE|URL|ENDPOINT|HOST|API)", n)
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None, None


# --------------------------------------------------------------- emitter probe

_EMITTER_CACHE: dict[tuple[str, str], tuple[bool, str | None]] = {}


def emitter_info(target: Any) -> tuple[bool, str | None, frozenset[str]]:
    """Does this function itself issue the HTTP request, and with what method?

    Returns (is_emitter, fixed_method, all_methods). fixed_method is None when
    the function takes the verb from its caller (``client.request(method, url)``).
    all_methods holds every verb the body can issue — Slack-style helpers post
    when given a body and get otherwise, so the caller decides.
    """
    key = (getattr(target, "__module__", "") or "", getattr(target, "__qualname__", "") or "")
    if key in _EMITTER_CACHE:
        return _EMITTER_CACHE[key]
    result: tuple[bool, str | None, frozenset[str]] = (False, None, frozenset())
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(target)))
    except Exception:
        _EMITTER_CACHE[key] = result
        return result

    client_names = http_client_names(tree)
    found: list[str | None] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr = node.func.attr
        if attr not in CLIENT_VERBS:
            continue
        if not is_http_client(node.func.value, client_names):
            continue
        if attr == "request":
            literal = render_str(node.args[0] if node.args else None)
            found.append(literal.upper() if literal and literal.upper() in HTTP_METHODS else None)
        else:
            found.append(attr.upper())

    if found:
        methods = frozenset(m for m in found if m)
        fixed = found[0] if len(methods) == 1 and found[0] else None
        result = (True, fixed, methods)

    _EMITTER_CACHE[key] = result
    return result


_EMITTER_BASE_CACHE: dict[tuple[str, str], str | None] = {}


def emitter_base(target: Any) -> str | None:
    """Base URL an api helper prepends, read from its own `url = f"{BASE}{path}"`.

    More precise than scanning the module for a likely-looking constant: a
    vendor module often defines several bases (SEMrush has four) and only the
    one this helper actually uses is correct.
    """
    key = (getattr(target, "__module__", "") or "", getattr(target, "__qualname__", "") or "")
    if key in _EMITTER_BASE_CACHE:
        return _EMITTER_BASE_CACHE[key]
    result: str | None = None
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(target)))
        consts = {
            name: value
            for name, value in (getattr(target, "__globals__", {}) or {}).items()
            if isinstance(value, str) and name.isupper() and value
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "url" for t in node.targets):
                continue
            rendered = render_str(node.value, {}, 0, consts)
            if rendered and rendered.startswith("http"):
                # Drop the trailing {path}/{endpoint} placeholder.
                result = re.sub(r"\{[\w]+\}/?$", "", rendered).rstrip("/")
                break
    except Exception:
        result = None
    _EMITTER_BASE_CACHE[key] = result
    return result


_EMITTER_FIXED_PATH_CACHE: dict[tuple[str, str], str | None] = {}


def emitter_fixed_path(target: Any) -> str | None:
    """The emitter's own literal path, when it is not parameterized by callers.

    Odoo funnels every operation through ``POST {base}/jsonrpc``; Slack instead
    builds ``{base}/{method}`` from the caller's argument. Only the former has a
    fixed path, and telling them apart stops a JSON-RPC operation name being
    recorded as if it were a URL path.
    """
    key = (getattr(target, "__module__", "") or "", getattr(target, "__qualname__", "") or "")
    if key in _EMITTER_FIXED_PATH_CACHE:
        return _EMITTER_FIXED_PATH_CACHE[key]
    result: str | None = None
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(target)))
        consts = {
            name: value
            for name, value in (getattr(target, "__globals__", {}) or {}).items()
            if isinstance(value, str) and name.isupper() and value
        }
        locals_map = collect_locals(tree)
        client_names = http_client_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in CLIENT_VERBS or not is_http_client(node.func.value, client_names):
                continue
            kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            if node.func.attr == "request":
                url_node = node.args[1] if len(node.args) > 1 else kwargs.get("url")
            else:
                url_node = node.args[0] if node.args else kwargs.get("url")
            rendered = render_str(url_node, locals_map, 0, consts)
            if not rendered:
                continue
            _, path = split_base(rendered)
            if path and not re.search(r"\{[\w]+\}", path) and path not in {"/", ""}:
                result = path
                break
    except Exception:
        result = None
    _EMITTER_FIXED_PATH_CACHE[key] = result
    return result


QUERY_DISCRIMINATORS = ("type", "action", "cmd", "operation")


def query_discriminator(node: ast.Call) -> str | None:
    """`params={"type": "domain_ranks"}` -> 'type=domain_ranks'."""
    for kw in node.keywords:
        if kw.arg not in {"params", "query"} or not isinstance(kw.value, ast.Dict):
            continue
        for key, value in zip(kw.value.keys, kw.value.values):
            if (
                isinstance(key, ast.Constant)
                and key.value in QUERY_DISCRIMINATORS
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                return f"{key.value}={value.value}"
    return None


def bind_call_args(target: Any, node: ast.Call) -> dict[str, ast.AST]:
    """Map a call's arguments onto the callee's real parameter names."""
    bound: dict[str, ast.AST] = {}
    try:
        params = list(inspect.signature(target).parameters.values())
    except Exception:
        params = []
    positional = [
        p.name
        for p in params
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    for index, arg in enumerate(node.args):
        if index < len(positional):
            bound[positional[index]] = arg
    for kw in node.keywords:
        if kw.arg:
            bound[kw.arg] = kw.value
    return bound


def default_method(target: Any) -> str | None:
    try:
        param = inspect.signature(target).parameters.get("method")
    except Exception:
        return None
    if param is not None and isinstance(param.default, str):
        if param.default.upper() in HTTP_METHODS:
            return param.default.upper()
    return None


# ------------------------------------------------------------------- guards


def guard_literals(test: ast.AST) -> set[str] | None:
    literals: set[str] = set()
    found = False
    for node in ast.walk(test):
        if isinstance(node, ast.Compare):
            left = node.left
            name = left.id if isinstance(left, ast.Name) else None
            if name is None and isinstance(left, ast.Attribute):
                name = left.attr
            if name not in ACTION_VARS:
                continue
            found = True
            for op, comparator in zip(node.ops, node.comparators):
                if isinstance(op, (ast.Eq, ast.In)):
                    if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
                        literals.add(comparator.value)
                    elif isinstance(comparator, (ast.Set, ast.List, ast.Tuple)):
                        for elt in comparator.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                literals.add(elt.value)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in {"startswith", "endswith"}:
                obj = node.func.value
                name = obj.id if isinstance(obj, ast.Name) else None
                if name in ACTION_VARS:
                    found = True
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            literals.add(arg.value)
                        elif isinstance(arg, (ast.Set, ast.List, ast.Tuple)):
                            for elt in arg.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    literals.add(elt.value)
    if not found or not literals:
        return None
    return literals


def guard_allows(action: str, literals: set[str]) -> bool:
    suffix = action.split(".", 1)[1] if "." in action else action
    tail = action.rsplit(".", 1)[-1]
    for lit in literals:
        if lit in {action, suffix, tail}:
            return True
        if action.startswith(lit) or lit.startswith(action):
            return True
    return False


# ------------------------------------------------------------------- walking


def walk_function(
    fn: Any,
    walk: Walk,
    depth: int,
    param_values: dict[str, str] | None = None,
) -> None:
    if depth > 6 or not hasattr(fn, "__code__"):
        return
    param_values = param_values or {}
    ident = (
        getattr(fn, "__module__", "") or "",
        getattr(fn, "__qualname__", "") or "",
        tuple(sorted(param_values.items())),
    )
    if ident in walk.visited:
        return
    walk.visited.add(ident)

    try:
        raw = inspect.getsource(fn)
        file = inspect.getsourcefile(fn)
        offset = fn.__code__.co_firstlineno - 1
    except Exception as exc:
        walk.notes.append(f"source unavailable for {ident[1]}: {exc}")
        return
    try:
        tree = ast.parse(textwrap.dedent(raw))
    except SyntaxError as exc:
        walk.notes.append(f"parse failed for {ident[1]}: {exc}")
        return

    globs = getattr(fn, "__globals__", {}) or {}
    closure = closure_map(fn)
    imported = local_imports(tree)
    locals_map = collect_locals(tree)
    client_names = http_client_names(tree)
    consts = {
        name: value
        for name, value in globs.items()
        if isinstance(value, str) and name.isupper() and value
    }
    # Literal arguments the caller passed in: lets a shared paginator whose
    # path arrives as a parameter (`_paginate(base, token, "/jobRequisitions")`)
    # still resolve to a real endpoint.
    consts.update(param_values)
    source_file = rel(file)

    def line_of(node: ast.AST) -> str:
        return f"{source_file}:{getattr(node, 'lineno', 0) + offset}"

    def resolve(name: str, func_node: ast.AST | None = None) -> Any:
        if name in closure:
            return closure[name]
        if name in imported:
            return imported[name]
        if name in globs:
            return globs[name]
        if isinstance(func_node, ast.Attribute) and isinstance(func_node.value, ast.Name):
            container = resolve(func_node.value.id)
            if container is not None:
                return getattr(container, name, None)
        return None

    def record(
        method: str | None,
        path: str | None,
        node: ast.Call,
        emitter: Any,
        trusted: bool = False,
        operation: str | None = None,
    ) -> bool:
        if not method or not path:
            return False
        method = method.upper()
        if method not in HTTP_METHODS:
            return False
        # `trusted` means the callee's own signature named this argument the
        # path/url, so vendors that pass bare resources ("Patient", "deals")
        # are honoured. Untrusted values come from a guessed positional arg.
        if not trusted and not looks_like_path(path):
            walk.notes.append(f"rejected non-path {method} {path!r} at {line_of(node)}")
            return False
        base_const, clean_path = split_base(path)
        target_fn = emitter if emitter is not None else fn
        base_value = emitter_base(target_fn)
        base_name = None
        if base_value is None:
            base_name, base_value = module_base(target_fn)
        if base_value is None and base_const and base_const.startswith("http"):
            base_value = base_const
        if not clean_path.startswith(("/", "http")):
            clean_path = "/" + clean_path
        walk.endpoints.append(
            Endpoint(
                method=method,
                path=clean_path,
                base=base_value,
                base_const=base_name,
                source=line_of(node),
                operation=operation,
            )
        )
        return True

    def handle_graphql(target: Any, node: ast.Call) -> None:
        doc = None
        for arg in list(node.args) + [kw.value for kw in node.keywords]:
            text = render_str(arg, locals_map, 0, consts)
            if text and re.search(r"\b(query|mutation|subscription)\b", text):
                doc = text
                break
        url = None
        try:
            src = textwrap.dedent(inspect.getsource(target))
            m = re.search(r"""["'](https?://[^"']+)["']""", src)
            if m:
                url = m.group(1)
        except Exception:
            pass
        if url is None:
            _, url = module_base(target)
        walk.endpoints.append(
            Endpoint(
                method="POST",
                path=url or "graphql",
                base=url,
                base_const=None,
                source=line_of(node),
                style="graphql",
                graphql_op=graphql_operation(doc) if doc else None,
            )
        )

    def handle_call(node: ast.Call, guards: list[set[str]]) -> None:
        func = node.func

        # direct httpx/client call in this very function
        if isinstance(func, ast.Attribute) and func.attr in CLIENT_VERBS:
            if is_http_client(func.value, client_names):
                kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
                if func.attr == "request":
                    method = render_str(
                        node.args[0] if node.args else kwargs.get("method"), locals_map, 0, consts
                    )
                    url_node = node.args[1] if len(node.args) > 1 else kwargs.get("url")
                else:
                    method = func.attr.upper()
                    url_node = node.args[0] if node.args else kwargs.get("url")
                record(method, render_str(url_node, locals_map, 0, consts), node, fn)
                return

        callee_name = None
        if isinstance(func, ast.Name):
            callee_name = func.id
        elif isinstance(func, ast.Attribute):
            callee_name = func.attr
        if not callee_name:
            return

        target = resolve(callee_name, func)
        if not callable(target) or not hasattr(target, "__code__"):
            return
        module = getattr(target, "__module__", "") or ""
        if not module.startswith("app."):
            return

        if "graphql" in callee_name.lower():
            handle_graphql(target, node)
            return

        is_emitter, fixed_method, all_methods = emitter_info(target)
        if is_emitter:
            bound = bind_call_args(target, node)
            method = None
            method_literal = render_str(bound.get("method"), locals_map, 0, consts)
            if method_literal and method_literal.upper() in HTTP_METHODS:
                method = method_literal.upper()
            if not method:
                method = fixed_method or default_method(target)
            path = None
            for name in PATH_ARG_NAMES:
                if name in bound:
                    path = render_str(bound[name], locals_map, 0, consts)
                    if path:
                        break
            operation = None
            if method_literal and method_literal.upper() not in HTTP_METHODS:
                fixed_path = emitter_fixed_path(target)
                if fixed_path:
                    # JSON-RPC style: one endpoint, operation named in the body.
                    path = path or fixed_path
                    operation = method_literal
                elif path is None:
                    # Slack style: the `method` argument IS the URL path.
                    path = method_literal
            # Query-discriminated APIs (SEMrush): the path is bare and the real
            # report is selected by a literal `type=` parameter at the call site.
            if path in {"/", ""} or (path or "").endswith("/"):
                disc = query_discriminator(node)
                if disc:
                    path = f"{path.rstrip('/')}/?{disc}"
            if method is None and len(all_methods) > 1:
                body_kwargs = {"json_body", "json", "body", "data", "payload"}
                has_body = any(kw.arg in body_kwargs for kw in node.keywords if kw.arg)
                method = "POST" if has_body else "GET"
            if record(method, path, node, target, trusted=True, operation=operation):
                return

        if SKIP_CALLEE_RE.search(callee_name):
            return
        if guards and not any(guard_allows(walk.action, g) for g in guards):
            return
        passed: dict[str, str] = {}
        for name, arg_node in bind_call_args(target, node).items():
            literal = render_str(arg_node, locals_map, 0, consts)
            if literal:
                passed[name] = literal
        walk_function(target, walk, depth + 1, passed)

    def visit(node: ast.AST, guards: list[set[str]]) -> None:
        if isinstance(node, ast.If):
            literals = guard_literals(node.test)
            if literals is None:
                for stmt in node.body:
                    visit(stmt, guards)
            elif guard_allows(walk.action, literals):
                for stmt in node.body:
                    visit(stmt, guards + [literals])
            for stmt in node.orelse:
                visit(stmt, guards)
            return
        if isinstance(node, ast.Call):
            handle_call(node, guards)
        for child in ast.iter_child_nodes(node):
            visit(child, guards)

    for stmt in tree.body:
        visit(stmt, [])


# ---------------------------------------------------------------- ranking


def rank_candidates(action: str, endpoints: list[Endpoint]) -> list[Endpoint]:
    suffix = action.split(".", 1)[1] if "." in action else action
    tail = suffix.rsplit(".", 1)[-1]
    resource = suffix.rsplit(".", 1)[0] if "." in suffix else suffix
    resource_words = {w for w in re.split(r"[._]", resource) if len(w) > 2}
    expected = VERB_EXPECTED_METHOD.get(tail, set())

    def score(endpoint: Endpoint) -> tuple:
        path_l = endpoint.path.lower()
        resource_hit = any(w in path_l or w.rstrip("s") in path_l for w in resource_words)
        method_hit = endpoint.method in expected if expected else False
        # A search verb genuinely maps to POST .../search on several vendors.
        search_hit = tail == "search" and "search" in path_l
        # get/update/delete address one record: the id-bearing path wins over a
        # sibling collection call used only as a lookup fallback.
        id_hit = tail in {"get", "update", "delete"} and bool(re.search(r"\{[\w]+\}", endpoint.path))
        return (
            -int(resource_hit),
            -int(method_hit),
            -int(id_hit),
            -int(search_hit),
            endpoint.source,
        )

    return sorted(endpoints, key=score)


# ------------------------------------------------------ provenance resolvers


def name_inferred_entry(action: str) -> dict[str, Any]:
    vendor, _, suffix = action.partition(".")
    method, path_template, _ = _infer_route(suffix)
    profile = VENDOR_HTTP_PROFILES.get(vendor)
    base = profile.base_url if profile else None
    prefix = (profile.path_prefix or "") if profile else ""
    return {
        "action": action,
        "provenance": "name_inferred",
        "method": method,
        "path": f"{prefix}{path_template}",
        "base_url": base,
        "api_reference": f"{method} {prefix}{path_template}",
        "source": "backend/app/connectors/catalog_http/executor.py:50 (_infer_route)",
        "vendor_validated": False,
        "note": (
            "Route computed from the action suffix by _infer_route() at import time. "
            "This is genuinely what the process sends, but it has never been checked "
            "against the vendor's published API."
        ),
    }


def twilio_entries() -> dict[str, dict[str, Any]]:
    from app.connectors import twilio_api

    src_line: dict[str, int] = {}
    try:
        lines = Path(inspect.getsourcefile(twilio_api)).read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            m = re.search(r'"(twilio\.[\w.]+)"\s*:', line)
            if m:
                src_line[m.group(1)] = idx
    except Exception:
        pass
    out: dict[str, dict[str, Any]] = {}
    for action, (method, path) in twilio_api._ROUTES.items():
        out[action] = {
            "action": action,
            "provenance": "route_table",
            "method": method,
            "path": path,
            "base_url": twilio_api.BASE,
            "api_reference": f"{method} {path}",
            "source": f"backend/app/connectors/twilio_api.py:{src_line.get(action, 28)}",
            "vendor_validated": False,
        }
    return out


def main() -> int:
    specs = catalog_specs()
    twilio = twilio_entries()

    entries: dict[str, dict[str, Any]] = {}
    undetermined: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    no_endpoint: list[dict[str, Any]] = []
    unreviewed: list[str] = []
    counts: Counter[str] = Counter()

    for action in specs:
        manual = manual_reference(action)
        if manual is not None:
            entry = {
                "action": action,
                "provenance": "manual_verified",
                "kind": manual.kind,
                "method": manual.method,
                "path": manual.path,
                "base_url": manual.base_url,
                "api_reference": manual.api_reference,
                "source": manual.source,
                "reviewed": REVIEWED,
                "note": manual.note,
                "vendor_validated": False,
            }
            if manual.api_reference is None:
                # Distinct from manual_verified: there is no vendor endpoint to
                # verify at all. Collapsing the two would tell a drift scan an
                # SMTP send is a hand-read REST route with a missing path.
                entry["provenance"] = "no_vendor_endpoint"
                entry["no_vendor_endpoint"] = True
                no_endpoint.append(entry)
                counts[f"no_endpoint_{manual.kind}"] += 1
            else:
                counts["manual_verified"] += 1
            entries[action] = entry
            continue

        if action in twilio:
            entries[action] = twilio[action]
            counts["route_table"] += 1
            continue

        key, fn = resolve_executor(action)
        if fn is None:
            undetermined.append({"action": action, "reason": "no executor registered"})
            counts["undetermined"] += 1
            continue

        module = getattr(fn, "__module__", "") or ""
        if module == "app.connectors.catalog_http.executor":
            entries[action] = name_inferred_entry(action)
            counts["name_inferred"] += 1
            continue

        walk = Walk(action=action)
        walk_function(fn, walk, 0)

        distinct: dict[tuple, Endpoint] = {}
        for endpoint in walk.endpoints:
            distinct.setdefault(endpoint.key(), endpoint)

        if not distinct:
            undetermined.append(
                {
                    "action": action,
                    "registry_key": key,
                    "module": module,
                    "reason": "no literal HTTP call site found in call graph",
                    "notes": walk.notes[:4],
                }
            )
            counts["undetermined"] += 1
            continue

        ordered = rank_candidates(action, list(distinct.values()))
        primary = ordered[0]
        review = None
        if len(ordered) > 1:
            review = ambiguity_verdict(action)
            if review is None:
                unreviewed.append(action)
            elif review.verdict == "corrected" and review.primary:
                match = next(
                    (e for e in ordered if e.reference() == review.primary), None
                )
                if match is None:
                    raise SystemExit(
                        f"{action}: review names primary {review.primary!r} but the "
                        f"extractor never found it: {[e.reference() for e in ordered]}"
                    )
                ordered = [match] + [e for e in ordered if e is not match]
                primary = match
            ambiguous.append(
                {
                    "action": action,
                    "module": module,
                    "chosen": primary.reference(),
                    "verdict": review.verdict if review else "UNREVIEWED",
                    "secondary_role": review.secondary_role if review else None,
                    "candidates": [
                        {"reference": e.reference(), "source": e.source} for e in ordered
                    ],
                }
            )
        entries[action] = {
            "action": action,
            # Multi-hit actions keep their own label all the way to the served
            # payload: the primary endpoint is a reviewed choice among several,
            # not the only thing the code can reach.
            "provenance": "dedicated" if len(ordered) == 1 else "dedicated_multi",
            "method": primary.method,
            "path": primary.path,
            "base_url": primary.base,
            "base_const": primary.base_const,
            "api_reference": primary.reference(),
            "style": primary.style,
            "graphql_op": primary.graphql_op,
            "operation": primary.operation,
            "source": primary.source,
            "registry_key": key,
            "module": module,
            "candidate_count": len(ordered),
            "endpoints": [
                {"reference": e.reference(), "source": e.source} for e in ordered
            ],
            "review": (
                {
                    "verdict": review.verdict,
                    "secondary_role": review.secondary_role,
                    "reviewed": AMBIGUITY_REVIEWED,
                }
                if review
                else None
            ),
            "vendor_validated": False,
        }
        counts["dedicated" if len(ordered) == 1 else "dedicated_multi"] += 1

    contract_hits = 0
    for action, entry in entries.items():
        contract = vendor_contract(action.split(".", 1)[0])
        if contract is None:
            entry["vendor_contract"] = None
            continue
        contract_hits += 1
        entry["vendor_contract"] = {
            "type": contract.contract_type,
            "url": contract.url,
            "verified_at": contract.verified_at,
            "note": contract.note or None,
        }

    out = {
        "catalog_action_total": len(specs),
        "mapped": len(entries),
        "counts": dict(counts),
        "undetermined_total": len(undetermined),
        "ambiguous_total": len(ambiguous),
        "no_vendor_endpoint_total": len(no_endpoint),
        "with_vendor_contract": contract_hits,
        "entries": entries,
        "undetermined": undetermined,
        "ambiguous": ambiguous,
        "no_vendor_endpoint": no_endpoint,
    }
    dest = REPO / "docs" / "delivery" / "api-reference-map.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")

    # Runtime slice: what the catalog API actually serves. Kept separate from the
    # full report so the shipped artifact carries only fields a consumer needs,
    # including the honesty flags — a name-inferred route must not be served as
    # if it were read out of vendor-confirmed code.
    runtime = {
        action: {
            k: v
            for k, v in {
                "api_reference": entry.get("api_reference"),
                "provenance": entry.get("provenance"),
                "source": entry.get("source"),
                "style": entry.get("style"),
                "base_url": entry.get("base_url"),
                "endpoints": (
                    [e["reference"] for e in entry["endpoints"]]
                    if entry.get("candidate_count", 1) > 1
                    else None
                ),
                "vendor_contract": (entry.get("vendor_contract") or {}).get("url"),
                "vendor_contract_type": (entry.get("vendor_contract") or {}).get("type"),
                "vendor_validated": entry.get("vendor_validated", False),
                "note": entry.get("note"),
            }.items()
            if v is not None
        }
        for action, entry in sorted(entries.items())
    }
    runtime_dest = (
        BACKEND / "app" / "connectors" / "action_catalog" / "data" / "api_reference_map.json"
    )
    runtime_dest.write_text(
        json.dumps({"generated_from": "scripts/build_api_reference_map.py", "actions": runtime}, indent=2),
        encoding="utf-8",
    )

    print(f"catalog actions      : {len(specs)}")
    print(f"mapped               : {len(entries)}")
    for name, count in counts.most_common():
        print(f"  {name:18s} {count:4d}")
    print(f"undetermined         : {len(undetermined)}")
    print(f"ambiguous (multi-hit): {len(ambiguous)}")
    print(f"no vendor endpoint   : {len(no_endpoint)}")
    print(f"with vendor contract : {contract_hits}")
    print(f"\nwrote {dest}")
    print(f"wrote {runtime_dest}")
    if unreviewed:
        print(
            f"\nUNREVIEWED multi-endpoint actions ({len(unreviewed)}) — add a verdict "
            f"to api_reference_review.py:"
        )
        for action in unreviewed:
            print(f"  {action}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
