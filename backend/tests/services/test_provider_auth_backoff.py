"""Offline authentication recovery contracts; no SDK, network or inference."""
import asyncio
import ast
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.providers.auth_backoff import (
    ProviderAuthBackoff,
    ProviderAuthenticationUnavailable,
    provider_auth_scope,
)


class RejectedCredential(Exception):
    status_code = 401


class AuthBackoffTests(unittest.TestCase):
    def test_rejected_key_is_suppressed_until_cooldown_and_then_recovers(self):
        now = [0.0]
        gate = ProviderAuthBackoff(clock=lambda: now[0])
        with self.assertRaises(ProviderAuthenticationUnavailable) as first:
            with gate.guard("openai", "private-key"):
                raise RejectedCredential("private-key and sensitive provider body")
        self.assertFalse(first.exception.suppressed)
        self.assertNotIn("private-key", str(first.exception))
        with self.assertRaises(ProviderAuthenticationUnavailable) as repeated:
            with gate.guard("openai", "private-key"):
                self.fail("must not invoke the provider")
        self.assertTrue(repeated.exception.suppressed)
        now[0] = 60.0
        with gate.guard("openai", "private-key"):
            pass

    def test_rotation_provider_and_endpoint_are_isolated(self):
        gate = ProviderAuthBackoff()
        with self.assertRaises(ProviderAuthenticationUnavailable):
            with gate.guard("openai", "old", "endpoint-a"):
                raise RejectedCredential()
        for args in [("openai", "new", "endpoint-a"), ("openai", "old", "endpoint-b"), ("anthropic", "old", "endpoint-a")]:
            with gate.guard(*args):
                pass

    def test_permission_rate_limit_transient_and_cancellation_do_not_block(self):
        gate = ProviderAuthBackoff()
        for status in [400, 403, 429, 500]:
            exc = RuntimeError("401 in arbitrary text is not authentication evidence")
            exc.status_code = status
            with self.assertRaises(RuntimeError):
                with gate.guard("openai", "key"):
                    raise exc
            with gate.guard("openai", "key"):
                pass
        with self.assertRaises(asyncio.CancelledError):
            with gate.guard("openai", "key"):
                raise asyncio.CancelledError()
        with gate.guard("openai", "key"):
            pass

    def test_response_status_and_bounded_cache(self):
        gate = ProviderAuthBackoff(capacity=2)
        for credential in ["one", "two", "three"]:
            exc = RuntimeError("not retained")
            exc.response = SimpleNamespace(status_code=401)
            with self.assertRaises(ProviderAuthenticationUnavailable):
                with gate.guard("openai", credential):
                    raise exc
        self.assertEqual(len(gate._blocked), 2)
        self.assertNotIn("three", repr(gate._blocked))

    def test_scope_uses_actual_client_and_matching_adapter_key(self):
        router = SimpleNamespace(settings=SimpleNamespace(openai_api_key="stale", gemini_key="chosen", gemini_api_key="other"))
        client = SimpleNamespace(api_key="actual", base_url="endpoint")
        self.assertEqual(provider_auth_scope(router, "openai", openai_client=client), ("actual", "endpoint"))
        self.assertEqual(provider_auth_scope(router, "gemini"), ("chosen", ""))


def load_dispatch(path, function, namespace):
    """Execute the real dispatch body isolated from unrelated app startup imports.

    This supplements full application tests; it does not certify SDK behavior.
    Internal imports, tool narrowing and metering in the body remain intact.
    """
    source = ast.parse(path.read_text())
    node = next(n for n in source.body if isinstance(n, ast.AsyncFunctionDef) and n.name == function)
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return namespace[function]


class DispatchContracts(unittest.IsolatedAsyncioTestCase):
    async def test_all_shared_provider_routes_back_off_without_switching(self):
        root = Path(__file__).resolve().parents[2] / "app/services"
        metering = types.ModuleType("app.services.tool_model_metering")
        metering.authorize_tool_model_call = AsyncMock()
        narrowed = types.ModuleType("app.services.narrowed_tools")
        narrowed.assert_tools_narrowed = lambda *args, **kwargs: None
        for provider in ["openai", "anthropic", "gemini"]:
            with self.subTest(provider=provider):
                gate = ProviderAuthBackoff()
                adapters = {name: AsyncMock(side_effect=RejectedCredential()) for name in ["openai", "anthropic", "gemini"]}
                call = load_dispatch(root / "providers/provider_tool_router.py", "complete_with_tools", {
                    "time": time, "resolve_provider_for_model": lambda model: provider,
                    **{f"_complete_{name}_with_tools": adapter for name, adapter in adapters.items()},
                })
                router = SimpleNamespace(settings=SimpleNamespace(openai_api_key="key", anthropic_api_key="key", gemini_api_key="key"), _openai=SimpleNamespace(api_key="key"))
                with patch.dict("sys.modules", {metering.__name__: metering, narrowed.__name__: narrowed}), patch("app.services.providers.auth_backoff.provider_auth_backoff", gate):
                    for _ in range(2):
                        with self.assertRaises(ProviderAuthenticationUnavailable):
                            await call(router, model="test", messages=[], tools=[])
                adapters[provider].assert_awaited_once()
                for name, adapter in adapters.items():
                    if name != provider:
                        adapter.assert_not_awaited()

    async def test_tool_narrowing_rejection_still_prevents_provider_execution(self):
        root = Path(__file__).resolve().parents[2] / "app/services"
        narrowed = types.ModuleType("app.services.narrowed_tools")
        def reject(*args, **kwargs):
            raise ValueError("tools_not_narrowed")
        narrowed.assert_tools_narrowed = reject
        call = load_dispatch(root / "providers/provider_tool_router.py", "complete_with_tools", {})
        with patch.dict("sys.modules", {narrowed.__name__: narrowed}):
            with self.assertRaisesRegex(ValueError, "tools_not_narrowed"):
                await call(SimpleNamespace(), model="test", messages=[], tools=[{}])

    async def test_unified_auth_failure_blocks_classical_call_with_same_key(self):
        root = Path(__file__).resolve().parents[2] / "app/services"
        gate = ProviderAuthBackoff()
        authorize = AsyncMock()
        metering = types.ModuleType("app.services.tool_model_metering")
        metering.authorize_tool_model_call = authorize
        narrowed = types.ModuleType("app.services.narrowed_tools")
        checked = []
        narrowed.assert_tools_narrowed = lambda tools, **kwargs: checked.append(tools)
        provider_module = types.ModuleType("app.services.providers.provider_tool_router")
        provider_module.resolve_provider_for_model = lambda model: "openai"
        provider_module.complete_with_tools = AsyncMock()
        streaming = AsyncMock(side_effect=RejectedCredential("secret response"))
        classical = AsyncMock()
        unified = load_dispatch(root / "unified_turn_reasoning_service.py", "_complete_unified_turn", {
            "asyncio": asyncio, "time": time, "_complete_unified_turn_stream": streaming,
        })
        tools = load_dispatch(root / "providers/provider_tool_router.py", "complete_with_tools", {
            "time": time, "resolve_provider_for_model": lambda model: "openai",
            "_complete_openai_with_tools": classical,
            "make_openai_compatible_response": lambda result: result,
            "logger": SimpleNamespace(debug=lambda *args: None),
        })
        client = SimpleNamespace(api_key="same-key", base_url="same-endpoint")
        router = SimpleNamespace(_openai=client, settings=SimpleNamespace(openai_api_key="same-key"))
        with patch.dict("sys.modules", {
            metering.__name__: metering, narrowed.__name__: narrowed,
            provider_module.__name__: provider_module,
        }), patch("app.services.providers.auth_backoff.provider_auth_backoff", gate):
            with self.assertRaises(ProviderAuthenticationUnavailable) as first:
                await unified(router, client, model="gpt-test", kwargs={}, wall_start=0, model_start=0)
            with self.assertRaises(ProviderAuthenticationUnavailable) as second:
                await tools(router, model="gpt-test", messages=[], tools=[])
            self.assertFalse(first.exception.suppressed)
            self.assertTrue(second.exception.suppressed)
            streaming.assert_awaited_once()
            classical.assert_not_awaited()
            self.assertEqual(checked, [[]])
            # A rotated credential immediately reaches the existing dispatch.
            client.api_key = "rotated-key"
            classical.return_value = SimpleNamespace(tool_calls=[])
            await tools(router, model="gpt-test", messages=[], tools=[])
            classical.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
