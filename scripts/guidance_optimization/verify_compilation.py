"""Credential-free, network-denied actual DSPy compile certification for CI."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import subprocess

# Remove credentials before importing DSPy/LiteLLM. This worker never generates.
for name in list(os.environ):
    if any(s in name.upper() for s in ("TOKEN", "API_KEY", "SECRET", "PASSWORD", "CREDENTIAL")):
        os.environ.pop(name, None)
attempts=[]

def deny(*args, **kwargs):
    attempts.append(True)
    raise RuntimeError("offline_compile_network_forbidden")
socket.socket.connect=deny
socket.socket.connect_ex=deny
socket.create_connection=deny
socket.getaddrinfo=deny

from optimize import compile_candidates, corpus, CORPUS_SHA256, sdk

candidates=compile_candidates()
training={(r["user"],r["assistant"]) for r in corpus()["train"]}
assert len(candidates)==3 and len({c["version"] for c in candidates})==3
assert [len(c["demos"]) for c in candidates]==[2,4,6]
assert all((d["user"],d["assistant"]) in training for c in candidates for d in c["demos"])
assert not attempts
cache=sdk().cache
assert cache.enable_disk_cache is False and cache.enable_memory_cache is False
import diskcache
import filelock
for blocked in (lambda:filelock.FileLock("/tmp/forbidden.lock").acquire(),
                lambda:diskcache.Disk.fetch(None,0,False,0,b"untrusted")):
    try:
        blocked()
    except RuntimeError as exc:
        assert str(exc)=="optimizer_disk_cache_and_file_locks_forbidden"
    else:
        raise AssertionError("storage_guard_not_enforced")
root=Path(__file__).resolve().parents[2]
files=["scripts/guidance_optimization/optimize.py","scripts/guidance_optimization/corpus.json",
       "scripts/guidance_optimization/requirements.lock","backend/app/services/guidance_optimization.py",
       "backend/app/services/conversational_behavior.py","backend/app/services/guidance_versions/active.json",
       "scripts/guidance_optimization/verify_compilation.py","scripts/guidance_optimization/verify_transport.py",
       "scripts/guidance_optimization/audit.py"]
report={"schema":1,"status":"SDK_COMPILATION_PASS","evidence_mode":"real_sdk_offline_compile",
        "dspy_version":"3.2.1","corpus_sha256":CORPUS_SHA256,"candidates":[c["version"] for c in candidates],
        "external_attempts":len(attempts),"provider_quality":"NOT_RUN","physical_voice":"NOT_RUN",
        "automatic_promotion":False,"production_certified":False,
        "source_sha":subprocess.check_output(["git", "rev-parse", "HEAD"],cwd=root,text=True).strip(),
        "source_dirty":bool(subprocess.check_output(["git", "status", "--porcelain"],cwd=root,text=True).strip()),
        "source_hashes":{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files}}
Path(sys.argv[1]).write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({k:v for k,v in report.items() if k!="source_hashes"}))
