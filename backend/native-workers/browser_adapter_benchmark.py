"""Real adapter microbenchmark inside the same gVisor image, without a model.

The local HTTP fixture is synthetic and confined to the guest loopback device.
This probes SDK control/readback plus shared approval-evidence primitives; it
does not certify an alternative production executor, HTTPS gateway, provider
quality, tenant authorization or a complete adapter-selection gate.
"""
from __future__ import annotations

import asyncio
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import resource
from pathlib import Path
from statistics import median
import subprocess
import signal
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from engine import configure_browser_sdk, fresh_browser_evidence, stable_browser_evidence,ensure_rejecting_dialog_handlers,close_dialog_handlers
except ModuleNotFoundError as error:
    if error.name != 'engine':
        raise
    from app.services.native_runtime.engine import configure_browser_sdk, fresh_browser_evidence, stable_browser_evidence,ensure_rejecting_dialog_handlers,close_dialog_handlers

TRIALS = 5
ACTION_TIMEOUT = 10
PAGE = b'''<!doctype html><title>Adapter fixture</title>
<h1>Deterministic adapter fixture</h1><p id="ready">Loading</p>
<button id="commit" onclick="fetch('/write',{method:'POST'}).then(()=>document.querySelector('#result').textContent='Written')">Commit synthetic change</button>
<p id="result">No change</p><p id="revision">Original</p>
<script>setTimeout(()=>document.querySelector('#ready').textContent='Ready',100);
setInterval(()=>fetch('/state').then(r=>r.json()).then(s=>document.querySelector('#revision').textContent=s.mutated?'Changed':'Original'),50)</script>'''


class Fixture:
    def __init__(self):
        self.writes = 0
        self.mutated = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/page')
                    self.end_headers()
                    return
                if self.path == '/page':
                    body, kind = PAGE, 'text/html'
                elif self.path == '/state':
                    body, kind = json.dumps({'mutated': owner.mutated}).encode(), 'application/json'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                if self.path != '/write':
                    self.send_error(404)
                    return
                owner.writes += 1
                self.send_response(204)
                self.end_headers()

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class PlaywrightSession:
    """Comparison-only shim exposing the production evidence function's inputs."""
    def __init__(self, page):
        self.page = page

    async def get_browser_state_summary(self, **_):
        value = await self.page.evaluate('''() => ({url:location.href,title:document.title,
            dom:document.body.innerText,buttons:[...document.querySelectorAll('button')].map(b=>({id:b.id,label:b.textContent,type:b.getAttribute('type')}))})''')
        nodes = {i + 1: SimpleNamespace(node_name='BUTTON', attributes={'id': b['id'], 'aria-label': b['label'], 'type': b.get('type')})
                 for i, b in enumerate(value['buttons'])}
        return SimpleNamespace(url=value['url'], title=value['title'], screenshot=None,
                               dom_state=SimpleNamespace(selector_map=nodes, llm_representation=lambda: value['dom']))

    async def take_screenshot(self, **_):
        return await self.page.screenshot(type='png', full_page=False, timeout=ACTION_TIMEOUT * 1000)


async def wait_state(session, text):
    deadline = time.monotonic() + ACTION_TIMEOUT
    while time.monotonic() < deadline:
        state = await session.get_browser_state_summary(include_screenshot=False, cached=False)
        if text in state.dom_state.llm_representation():
            return state
        await asyncio.sleep(.1)
    raise TimeoutError('Bounded fixture readback failed')


def action_for(state):
    for index, node in state.dom_state.selector_map.items():
        if (node.attributes or {}).get('id') == 'commit':
            return {'click': {'index': index}}
    raise AssertionError('Fixture action absent from observed DOM')


async def reviewed_click(session, action, execute, *, approved, cancelled=False, mutate=None, authority=None):
    before_state, before = await stable_browser_evidence(session, action)
    if mutate is not None:
        mutate()
        await wait_state(session, 'Changed')
    if not approved or cancelled:
        raise PermissionError('Fixture authority denied')
    if authority is not None:
        await authority(action, before)
    after_state, after = await fresh_browser_evidence(session, action, 'after_approval')
    if before != after:
        error = PermissionError('Fixture context changed after review')
        # Fixed boolean diagnostics only: no DOM, URL, pixels or exception text.
        error.evidence_changes = {
            'url': before_state.url != after_state.url,
            'dom': before_state.dom_state.llm_representation() != after_state.dom_state.llm_representation(),
            'title': before.get('page_title') != after.get('page_title'),
            'targets': before.get('targets') != after.get('targets'),
            'fingerprint': before.get('page_fingerprint') != after.get('page_fingerprint'),
        }
        raise error
    await execute(action)


async def trial(adapter, number):
    from broker_process_contract import IndependentFixture, CrashBroker
    fixture = None
    child = None
    session = None
    driver = None
    connection = None
    stage = 'chromium_start'
    started = time.monotonic()
    initial_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    with tempfile.TemporaryDirectory(prefix='adapter-', dir='/workspace') as profile:
        fixture = IndependentFixture(Path(profile)/'write-counter.sqlite3', PAGE)
        try:
            # Both adapters attach to Chromium started with exactly these flags.
            # Chromium's sandbox stays enabled; no --no-sandbox fallback exists.
            child = subprocess.Popen(['/usr/bin/chromium', '--headless', '--no-first-run',
                '--no-default-browser-check', '--disable-background-networking', '--disable-dev-shm-usage',
                '--remote-debugging-port=9222', '--window-size=1280,720', '--user-data-dir=' + profile,
                'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            deadline = time.monotonic() + ACTION_TIMEOUT
            while True:
                if child.poll() is not None:
                    raise RuntimeError('Chromium exited before readiness')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=1) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Chromium readiness deadline')
                    await asyncio.sleep(.1)
            if adapter == 'browser_use':
                stage = 'adapter_connect'
                from browser_use import Browser, Tools
                configure_browser_sdk()
                session = Browser(cdp_url='http://127.0.0.1:9222', use_cloud=False,
                    allowed_domains=['http://127.0.0.1'], keep_alive=True,
                    viewport={'width': 1280, 'height': 720},
                    highlight_elements=False, dom_highlight_elements=False)
                await session.start()
                stage = 'dialog_readiness'
                await ensure_rejecting_dialog_handlers(session)
                tools = Tools(exclude_actions=['evaluate', 'write_file', 'replace_file', 'read_file',
                    'upload_file', 'save_as_pdf', 'search'])
                model = tools.registry.create_action_model()

                async def execute(action):
                    result = await tools.act(model(**action), browser_session=session, action_timeout=ACTION_TIMEOUT)
                    if result.error:
                        raise RuntimeError('SDK action failed')
            else:
                stage = 'adapter_connect'
                from playwright.async_api import async_playwright
                driver = await async_playwright().start()
                connection = await driver.chromium.connect_over_cdp('http://127.0.0.1:9222')
                page = connection.contexts[0].pages[0]
                await page.set_viewport_size({'width': 1280, 'height': 720})
                session = PlaywrightSession(page)

                async def execute(action):
                    if 'navigate' in action:
                        await page.goto(action['navigate']['url'], timeout=ACTION_TIMEOUT * 1000)
                    else:
                        await page.locator('#commit').click(timeout=ACTION_TIMEOUT * 1000)

            setup_ms = (time.monotonic() - started) * 1000
            before_navigation = time.monotonic()
            stage = 'navigation'
            await execute({'navigate': {'url': fixture.origin + '/redirect'}})
            stage = 'page_readback'
            state = await wait_state(session, 'Ready')
            assert state.url == fixture.origin + '/page' and state.title == 'Adapter fixture'
            navigation_ms = (time.monotonic() - before_navigation) * 1000
            action = action_for(state)
            # Initial navigation/readback is not the same as a settled viewport.
            # The fixture's asynchronously rendered Ready label has completed;
            # give Chromium one bounded paint interval before capturing the
            # unmodified production-grade stable evidence twice.
            await asyncio.sleep(0.5)
            snapshot_started = time.monotonic()
            stage = 'stable_snapshot'
            _, evidence = await stable_browser_evidence(session, action)
            assert len(evidence['page_fingerprint']) == 64
            snapshot_ms = (time.monotonic() - snapshot_started) * 1000
            click_started = time.monotonic()
            stage = 'approved_click'
            await reviewed_click(session, action, execute, approved=True)
            await wait_state(session, 'Written')
            assert fixture.writes == 1
            click_ms = (time.monotonic() - click_started) * 1000
            for options in ({'approved': False}, {'approved': True, 'cancelled': True},
                            {'approved': True, 'mutate': lambda: setattr(fixture, 'mutated', True)}):
                stage = 'stale_no_write' if 'mutate' in options else 'cancelled_no_write' if options.get('cancelled') else 'denied_no_write'
                try:
                    await reviewed_click(session, action, execute, **options)
                except PermissionError:
                    pass
                else:
                    raise AssertionError('Unapproved, cancelled or stale action executed')
                assert fixture.writes == 1
            # The browser and broker cannot edit the server-owned SQLite counter.
            # Kill the actual journal-owning OS process after its approval reply.
            recovery = None
            if number == 0:
                stage = 'broker_process_crash_restart'
                fixture.mutated = False
                await wait_state(session, 'Original')
                broker = None
                guarded = []
                async def crash_authority(requested_action, fingerprint):
                    nonlocal broker, recovery
                    broker = CrashBroker(Path(profile)/'private-broker')
                    request = broker.approve({'actions':requested_action, **fingerprint})
                    assert request['state'] == 'approved'
                    recovery = await asyncio.to_thread(broker.kill_and_restart)
                async def fenced_execute(requested_action):
                    guarded.append(True)
                    if not broker.authorized():
                        raise PermissionError('Restarted broker rejected stale approval')
                    await execute(requested_action)
                try:
                    try:
                        await reviewed_click(session, action, fenced_execute, approved=True, authority=crash_authority)
                    except PermissionError:
                        assert guarded == [True] and recovery is not None
                    else:
                        raise AssertionError('Crashed broker approval executed')
                    assert fixture.writes == 1
                    recovery['independent_writes_before'] = 1
                    recovery['independent_writes_after'] = fixture.writes
                    recovery['unauthorized_writes'] = fixture.writes - 1
                finally:
                    if broker is not None:broker.close()
            final_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            return {'adapter': adapter, 'trial': number, 'passed': True,
                'independent_server_process': True, 'unauthorized_writes': fixture.writes - 1,
                'broker_process_recovery': recovery,
                'total_elapsed_ms': (time.monotonic() - started) * 1000,
                'child_cpu_ms': max(0.0, (final_usage.ru_utime + final_usage.ru_stime - initial_usage.ru_utime - initial_usage.ru_stime) * 1000),
                'child_peak_rss_kib': final_usage.ru_maxrss,
                'setup_ms': setup_ms,
                'navigation_ms': navigation_ms, 'snapshot_ms': snapshot_ms, 'approved_click_ms': click_ms,
                'checks': ['redirect', 'dynamic_dom', 'url_title_readback', 'actual_screenshot',
                           'approved_click_readback', 'denial_no_write', 'cancelled_no_write', 'stale_no_write', 'independent_server_write_counter']}
        except Exception as error:
            error.benchmark_stage = stage
            raise
        finally:
            try:
                if adapter == 'browser_use' and session is not None:
                    await close_dialog_handlers(session)
                    await asyncio.wait_for(session.kill(), timeout=10)
                if connection is not None:
                    await connection.close()
                if driver is not None:
                    await driver.stop()
            finally:
                if child is not None:
                    try:
                        os.killpg(child.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=5)
                    # The parent can exit before Chromium descendants. A fresh
                    # trial must not attach to the previous process's CDP port.
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if fixture is not None:fixture.close()


async def run():
    rows = []
    # Alternate trial order to avoid always giving one adapter a warm host.
    for number in range(TRIALS):
        order = ('browser_use', 'playwright') if number % 2 == 0 else ('playwright', 'browser_use')
        for adapter in order:
            try:
                rows.append(await asyncio.wait_for(trial(adapter, number), timeout=90))
            except Exception as error:
                # No SDK exception body, page content or process log is exported.
                rows.append({'adapter': adapter, 'trial': number, 'passed': False,
                             'failure_class': type(error).__name__,
                             'evidence_changes': getattr(error, 'evidence_changes', {}),
                             'failure_stage': getattr(error, 'benchmark_stage', 'trial_timeout')})
    summary = {}
    for adapter in ('browser_use', 'playwright'):
        successful = [row for row in rows if row['adapter'] == adapter and row['passed']]
        summary[adapter] = {'completed': len(successful), 'attempted': TRIALS,
            **{key: median(row[key] for row in successful) if successful else None
               for key in ('setup_ms', 'navigation_ms', 'snapshot_ms', 'approved_click_ms', 'total_elapsed_ms', 'child_cpu_ms')}}
    import hashlib
    import importlib.metadata
    return {'schema_version': 1, 'evidence_kind': 'real_chromium_adapter_microbenchmark',
        'git_sha': os.environ.get('BENCHMARK_GIT_SHA', 'local'),
        'chromium_version': subprocess.check_output(['/usr/bin/chromium', '--version'], text=True).strip(),
        'libraries': {name: importlib.metadata.version(name) for name in ('browser-use', 'playwright')},
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'engine_sha256': hashlib.sha256(Path(__file__).with_name('engine.py').read_bytes()).hexdigest(),
        'fixture_sha256': __import__('hashlib').sha256(PAGE).hexdigest(),
        'measurement_limits': {'cpu': 'RUSAGE_CHILDREN cumulative differential; excludes parent and fixture server',
            'peak_rss': 'RUSAGE_CHILDREN process-high-water mark is cumulative across trials; not an attributable per-trial memory delta',
            'cost': 'No pricing or infrastructure utilization data supplied; monetary cost unmeasured',
            'reliability': 'Five fixture trials per adapter are diagnostic, not a statistically representative reliability estimate'},
        'thresholds': {'trials_per_adapter': TRIALS, 'required_correctness_rate': 1.0,
                       'allowed_unauthorized_writes': 0, 'per_trial_timeout_seconds': 90},
        'rows': rows, 'summary': summary, 'microbenchmark_passed': all(r['passed'] for r in rows),
        'production_adapter_selection': 'BLOCKED_PENDING_FULL_GATEWAY_AND_RUNTIME_COMPARISON',
        'unmeasured': ['production_gateway_parity', 'tenant_authorization', 'crash_recovery',
                       'provider_quality', 'operating_cost', 'maintenance_cost', 'representative_reliability'],
        'process_contract_scope': 'Owned guest-local server and real journal broker child; not production worker lifecycle or live tenant gateway',
        'broker_process_contract_sha256': hashlib.sha256(Path(__file__).with_name('broker_process_contract.py').read_bytes()).hexdigest(),
        'production_certified': False}


if __name__ == '__main__':
    # SDK logs stay private to this credential-free synthetic container.
    with contextlib.redirect_stdout(sys.stderr):
        report = asyncio.run(run())
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report['microbenchmark_passed'] else 1)
