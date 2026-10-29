import io
from pathlib import Path
import runpy
from types import SimpleNamespace
from unittest.mock import AsyncMock
import urllib.request

from PIL import Image
import pytest

benchmark = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'native-workers/browser_adapter_benchmark.py'))


class Session:
    def __init__(self):
        self.changed = False
        buffer = io.BytesIO()
        Image.new('RGB', (4, 4), 'white').save(buffer, format='PNG')
        self.pixels = buffer.getvalue()

    async def get_browser_state_summary(self, **_):
        dom = 'Changed' if self.changed else 'Original'
        node = SimpleNamespace(node_name='BUTTON', attributes={'id': 'commit', 'aria-label': 'Commit'})
        return SimpleNamespace(url='http://127.0.0.1/page', title='Fixture',
            dom_state=SimpleNamespace(selector_map={1: node}, llm_representation=lambda: dom))

    async def take_screenshot(self, **_):
        return self.pixels


@pytest.mark.asyncio
async def test_paired_probe_rejects_denied_cancelled_and_stale_actions_before_dispatch():
    session = Session()
    execute = AsyncMock()
    action = {'click': {'index': 1}}
    for options in ({'approved': False}, {'approved': True, 'cancelled': True},
                    {'approved': True, 'mutate': lambda: setattr(session, 'changed', True)}):
        with pytest.raises(PermissionError):
            await benchmark['reviewed_click'](session, action, execute, **options)
        execute.assert_not_awaited()
    await benchmark['reviewed_click'](session, action, execute, approved=True)
    execute.assert_awaited_once_with(action)


def test_local_fixture_redirect_readback_and_effect_counter():
    fixture = benchmark['Fixture']()
    try:
        assert fixture.server.server_address[0] == '127.0.0.1'
        with urllib.request.urlopen(fixture.origin + '/redirect', timeout=2) as response:
            assert response.url == fixture.origin + '/page'
            assert response.read() == benchmark['PAGE']
        assert fixture.writes == 0
        request = urllib.request.Request(fixture.origin + '/write', data=b'', method='POST')
        with urllib.request.urlopen(request, timeout=2) as response:
            assert response.status == 204
        assert fixture.writes == 1
    finally:
        fixture.close()


@pytest.mark.asyncio
async def test_playwright_readback_uses_rendered_text_not_script_literals():
    page = SimpleNamespace(evaluate=AsyncMock(return_value={
        'url': 'http://127.0.0.1/page', 'title': 'Fixture', 'dom': 'Loading',
        'buttons': [{'id': 'commit', 'label': 'Commit'}]}))
    state = await benchmark['PlaywrightSession'](page).get_browser_state_summary()
    assert state.dom_state.llm_representation() == 'Loading'
    assert 'document.body.innerText' in page.evaluate.call_args.args[0]
    assert 'outerHTML' not in page.evaluate.call_args.args[0]
    assert benchmark['action_for'](state) == {'click': {'index': 1}}


def test_benchmark_cost_and_reliability_evidence_is_explicitly_bounded():
    import inspect
    source = inspect.getsource(benchmark['run'])
    assert 'representative_reliability' in source
    assert 'production_gateway_parity' in source
    assert 'tenant_authorization' in source
    assert 'crash_recovery' in source
    assert 'child_cpu_ms' in source
    assert 'total_elapsed_ms' in source
    assert 'monetary cost unmeasured' in source


def test_strict_snapshot_gate_remains_active_after_fixture_paint_delay():
    import inspect
    source = inspect.getsource(benchmark["trial"])
    assert "await asyncio.sleep(0.5)" in source
    assert "await stable_browser_evidence(session, action)" in source
    assert source.index("await asyncio.sleep(0.5)") < source.index("await stable_browser_evidence(session, action)")
    assert "approved=True" in source
