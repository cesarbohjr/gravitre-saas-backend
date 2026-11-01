"""Read-only native-host readiness; no tenant jobs, grants or provider calls."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys


def check() -> None:
    source=Path('/opt/gravitre/backend')
    sys.path.insert(0,str(source))
    from app.services.native_runtime.docker_runner import SandboxImages
    images=SandboxImages(os.environ['NATIVE_OPENHANDS_IMAGE'],os.environ['NATIVE_BROWSER_IMAGE'],os.environ['NATIVE_GATEWAY_IMAGE'],os.environ.get('NATIVE_SANDBOX_RUNTIME','runsc'))
    images.validate()
    installed=json.loads(subprocess.check_output(['docker','info','--format','{{json .Runtimes}}'],timeout=20))
    if images.runtime not in installed:raise RuntimeError('Native isolating runtime is unavailable')
    for image in (images.openhands,images.browser_use,images.gateway):
        subprocess.run(['docker','image','inspect',image],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
    target=Path(os.environ['NATIVE_JOURNAL_PATH'])
    if not target.is_absolute() or not str(target).startswith('/var/lib/gravitre-native/') or target.parent.is_symlink():raise ValueError('Native journal must use the approved persistent directory')
    if not target.parent.is_dir() or target.parent.stat().st_mode & 0o077:raise ValueError('Native journal directory must exist with mode 0700')
    if target.exists() and (target.is_symlink() or target.stat().st_mode & 0o077):raise ValueError('Native journal must be a private regular file')
    for name in ('NATIVE_JOURNAL_KEY','NATIVE_CORRELATION_KEY','NATIVE_WORKER_SIGNING_KEY','NATIVE_TENANTS_JSON'):
        if not os.environ.get(name):raise ValueError('Required native secret configuration is missing')
    print('Native host preflight passed; no workload or telemetry was activated')


if __name__=='__main__':
    try:check()
    except Exception:
        print('Native host preflight failed; inspect private configuration and runtime readiness',file=sys.stderr)
        raise SystemExit(1) from None
