"""Three scheduled matched trials; failures are retained, never retried away."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from voice_paired_live import guard, TARGET


def main():
    guard(os.environ)
    from app.config import get_settings
    from supabase import create_client
    from mint_smoke_org_session import mint_session, export_to_github, AUTH_MODE
    settings = get_settings()
    if settings.supabase_url.rstrip('/') != TARGET:
        raise ValueError('acceptance settings mismatch')
    client = create_client(TARGET, settings.supabase_service_role_key)
    root = Path('acceptance-results/repeated-paired')
    root.mkdir(parents=True, exist_ok=True)
    raw = Path('/tmp/gravitre-paired')
    raw.mkdir(parents=True, exist_ok=True)
    report = {'git_sha': os.environ.get('ACCEPTANCE_SOURCE_SHA'),
        'status': 'RUNNING', 'certified': False, 'scheduled_repetitions': 3, 'runs': []}
    target = root / 'manifest.json'
    target.write_text(json.dumps(report, indent=2))
    for repetition in range(1, 4):
        for kind, script, variable, count in (
            ('voice', 'voice_paired_live.py', 'ACCEPTANCE_ARTIFACT_DIR', 10),
            ('native', 'voice_native_assignment_live.py', 'ACCEPTANCE_NATIVE_ARTIFACT_DIR', 4),
        ):
            folder = root / ('repetition-' + str(repetition)) / kind
            folder.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ)
            token, org = mint_session(env, client)
            export_to_github(token, org, Path(env['GITHUB_ENV']))
            env.update(PLATFORM_LIVE_BEARER_TOKEN=token, PLATFORM_LIVE_ORG_ID=org,
                PLATFORM_LIVE_AUTH_MODE=AUTH_MODE)
            env[variable] = str(folder)
            started = time.monotonic()
            # Pipeline logs can contain free text; portable evidence is the
            # bounded sanitized manifest and timing/WAV/sink artifacts only.
            with (raw / (kind + '-' + str(repetition) + '.log')).open('w') as log:
                try:
                    result = subprocess.run([sys.executable, str(Path(__file__).with_name(script))],
                        env=env, stdout=log, stderr=subprocess.STDOUT, timeout=900)
                    exit_code = result.returncode
                except subprocess.TimeoutExpired:
                    exit_code = 124
            evidence = folder / 'manifest.json'
            rows = json.loads(evidence.read_text()).get('trials', []) if evidence.exists() else []
            passed = exit_code == 0 and len(rows) == count and all(r.get('status') == 'PASS' for r in rows)
            report['runs'].append({'repetition': repetition, 'kind': kind,
                'status': 'PASS' if passed else 'FAIL', 'exit_code': exit_code,
                'manifest': str(evidence), 'elapsed_s': round(time.monotonic() - started, 2)})
            target.write_text(json.dumps(report, indent=2))
            print('ACCEPTANCE_REPETITION', repetition, kind, 'PASS' if passed else 'FAIL', flush=True)
    report['status'] = 'PASS' if len(report['runs']) == 6 and all(r['status'] == 'PASS' for r in report['runs']) else 'FAIL'
    target.write_text(json.dumps(report, indent=2))
    if report['status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
