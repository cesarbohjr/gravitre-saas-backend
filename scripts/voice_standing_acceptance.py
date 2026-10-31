"""Run the complete standing prompt batteries on the isolated, loopback API.

Real production routes/Auth/DB/provider calls; no lifespan schedulers or workers.
Raw logs/reports stay on the disposable runner. Portable evidence contains only
fixed verdicts, numeric/boolean observations and bounded diagnostic categories.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import contextlib
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
TARGET = 'https://aadnwmjzrmbvadszroqt.supabase.co'
ORG = 'f07e57c0-1501-4000-8000-c04e57a00001'
BASE = 'http://127.0.0.1:8790'
BATTERIES = (
    ('phase2', 'verify-unified-turn-phase2-live.py', 'unified-turn-phase2-battery-live.json'),
    ('persona', 'verify-unified-turn-persona-drift-live.py', 'unified-turn-persona-drift-live.json'),
    ('pending', 'verify-unified-turn-pending-fix-targeted-live.py', 'unified-turn-pending-fix-targeted-live.json'),
    ('mapper', 'verify-unified-turn-phase4-live.py', 'unified-turn-phase4-live-probe.json'),
    ('ttft', 'verify-unified-turn-task-ttft-live.py', 'unified-turn-task-ttft-live.json'),
    ('breakdown', 'verify-unified-turn-ttft-breakdown-live.py', 'unified-turn-ttft-breakdown-live.json'),
    ('injection', 'verify-unified-turn-prompt-injection-live.py', 'unified-turn-prompt-injection-live.json'),
)
VERDICTS = frozenset({'PASS', 'FAIL', 'NOT RUN', 'RUNNING', 'pass', 'fail'})
REPORT_KEYS = frozenset({
    'status', 'verdict', 'ok', 'passed', 'failed', 'cases', 'results', 'probes',
    'turns', 'functional_ok', 'functional_pass_n', 'functional_fail_n', 'total',
    'matrix', 'cutover_gates', 'ttft', 'latency_ms', 'elapsed_ms', 'exit_code',
    'classical_batteries', 'skipped', 'unified_live', 'unified_shadow', 'n',
    'count', 'p50_ms', 'p95_ms', 'min_ms', 'max_ms', 'error', 'fatal',
})


def validate_environment(env):
    if (env.get('GRAVITRE_VOICE_ISOLATED') != '1'
            or env.get('SUPABASE_URL', '').rstrip('/') != TARGET
            or env.get('E2E_SUPABASE_ALLOWED_URL', '').rstrip('/') != TARGET
            or env.get('ISOLATED_CONVERSATION_TEST_ORG_ID') != ORG
            or env.get('LIVE_API_BASE', BASE).rstrip('/') != BASE):
        raise ValueError('isolated acceptance target mismatch')
    for key in ('SUPABASE_SERVICE_ROLE_KEY', 'SUPABASE_JWT_SECRET', 'ANTHROPIC_API_KEY',
                'ISOLATED_CONVERSATION_TEST_USER_ID', 'ACCEPTANCE_SOURCE_SHA'):
        if not env.get(key):
            raise ValueError('missing:' + key)
    # Legacy battery loaders prefer dotenv files to the process environment.
    # Refuse them rather than permitting a fallback to another account/project.
    if any(p.exists() for p in (ROOT / '.env', ROOT / 'backend/.env',
                               ROOT / 'backend/.env.operator.local')):
        raise ValueError('dotenv override forbidden in acceptance')


def portable(value, depth=0):
    """Never export arbitrary report strings, dictionary keys or provider bodies."""
    if depth > 12:
        return None
    if value is None or type(value) in (bool, int, float):
        return value
    if isinstance(value, str):
        return value if value in VERDICTS else '[omitted]'
    if isinstance(value, list):
        return [portable(v, depth + 1) for v in value[:500]]
    if isinstance(value, dict):
        return {(k if k in REPORT_KEYS else 'field_' + str(i)): portable(v, depth + 1)
                for i, (k, v) in enumerate(list(value.items())[:150])}
    return None


def stop_group(process):
    # The leader may already have exited while one of phase2's children lives.
    # Always stop the entire isolated group, not just its original leader.
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def run_bounded(command, *, env, log, timeout):
    with log.open('w') as output:
        child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output,
            stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return 124
        finally:
            stop_group(child)


def run_batteries(env, output, raw, report):
    for label, script, filename in BATTERIES:
        source = ROOT / 'docs/delivery' / filename
        source.unlink(missing_ok=True)  # never accept a historical tracked result
        started = time.monotonic()
        code = run_bounded([sys.executable, str(ROOT / 'scripts' / script)],
            env=env, log=raw / (label + '.log'), timeout=1200 if label == 'phase2' else 600)
        present = source.is_file()
        row = {'battery': label, 'exit_code': code,
            'status': 'PASS' if code == 0 and present else 'FAIL',
            'report_present': present, 'elapsed_s': round(time.monotonic() - started, 2)}
        if present:
            try:
                data = json.loads(source.read_text())
                verdict = data.get('verdict', data.get('status'))
                row['reported_verdict'] = verdict if isinstance(verdict, str) and verdict in VERDICTS else None
                if row['reported_verdict'] in {'FAIL', 'fail', 'NOT RUN'}:
                    row['status'] = 'FAIL'
                (output / filename).write_text(json.dumps(portable(data), indent=2))
                source.replace(raw / filename)
            except (ValueError, OSError, AttributeError, TypeError):
                row.update(status='FAIL', diagnostic='invalid_report')
        diagnostic = (raw / (label + '.log')).read_text(errors='replace')[-128000:].lower()
        row['diagnostic_categories'] = [word for word in ('missing', 'connector', 'authorization',
            'budget', 'timeout', 'assertion', 'rate limit', '401', '403', '429', 'exception')
            if word in diagnostic]
        report['batteries'].append(row)
        (output / 'manifest.json').write_text(json.dumps(report, indent=2))
        print('ACCEPTANCE_STANDING', label, row['status'], flush=True)


def main():
    env = dict(os.environ)
    validate_environment(env)
    import httpx
    from supabase import create_client
    db = create_client(TARGET, env['SUPABASE_SERVICE_ROLE_KEY'])
    flags = db.table('organizations').select('settings').eq('id', ORG).single().execute().data['settings']
    if not all(flags.get(k) is True for k in ('never_customer_visible', 'isolated_conversation_test_org')):
        raise ValueError('smoke flags missing')
    if db.table('connectors').select('id').eq('org_id', ORG).limit(1).execute().data:
        raise ValueError('standing acceptance requires no real connector grants')
    env.update(LIVE_API_BASE=BASE, EXPECT_SHA=env['ACCEPTANCE_SOURCE_SHA'],
        GIT_SHA=env['ACCEPTANCE_SOURCE_SHA'], RAILWAY_GIT_COMMIT_SHA=env['ACCEPTANCE_SOURCE_SHA'],
        NOTIFICATION_EMAIL_ENABLED='false', UNIFIED_TURN_LIVE_ENABLED='true',
        UNIFIED_TURN_SHADOW_ENABLED='false', PHASE2_CASE_FILTER='all',
        PHASE2_SKIP_CLASSICAL='false', PERSONA_DRIFT_TURNS='30',
        PREFERRED_AI_PROVIDER='anthropic', OPENAI_API_KEY='', GEMINI_API_KEY='')
    output = ROOT / 'acceptance-results/standing-batteries'
    output.mkdir(parents=True, exist_ok=True)
    raw = Path('/tmp/gravitre-standing')
    raw.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    report = {'git_sha': env['ACCEPTANCE_SOURCE_SHA'], 'status': 'RUNNING',
        'certified': False, 'started_at': started, 'api_base': BASE,
        'scope': 'production routes with real Auth/DB/inference; lifespan workers disabled',
        'batteries': [], 'retired_job_ids': []}
    manifest = output / 'manifest.json'
    manifest.write_text(json.dumps(report, indent=2))
    # --lifespan off is essential: these tests never start platform schedulers,
    # assignment workers, notification delivery or domain-event relay workers.
    with (raw / 'server.log').open('w') as log:
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
            '--host', '127.0.0.1', '--port', '8790', '--lifespan', 'off'],
            cwd=ROOT / 'backend', env=env, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True)
        try:
            ready = False
            with httpx.Client(timeout=5) as http:
                for _ in range(120):
                    if server.poll() is not None:
                        raise RuntimeError('loopback API exited before readiness')
                    try:
                        health = http.get(BASE + '/health').json()
                        ready = health.get('git_sha') == env['ACCEPTANCE_SOURCE_SHA']
                    except (httpx.HTTPError, ValueError):
                        pass
                    if ready:
                        break
                    time.sleep(.5)
            if not ready:
                raise TimeoutError('loopback API readiness deadline')
            run_batteries(env, output, raw, report)
            report['status'] = 'PASS' if len(report['batteries']) == len(BATTERIES) and all(
                r['status'] == 'PASS' for r in report['batteries']) else 'FAIL'
        except Exception as error:
            report.update(status='FAIL', error_type=type(error).__name__)
        finally:
            stop_group(server)
            try:
                rows = db.table('agent_jobs').select('id,status').eq('org_id', ORG).eq(
                    'created_by', env['ISOLATED_CONVERSATION_TEST_USER_ID']).gte('created_at', started).limit(1001).execute().data
                if len(rows) > 1000:
                    report.update(status='FAIL', cleanup='unbounded_job_window')
                else:
                    for row in rows:
                        if row['status'] in {'queued', 'running', 'pending', 'paused'}:
                            db.table('agent_jobs').update({'status': 'cancelled',
                                'error': 'isolated standing acceptance retired; no worker executed'}).eq(
                                    'org_id', ORG).eq('id', row['id']).execute()
                            report['retired_job_ids'].append(row['id'])
            except Exception as error:
                report.update(status='FAIL', cleanup_error_type=type(error).__name__)
            finally:
                manifest.write_text(json.dumps(report, indent=2))
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
