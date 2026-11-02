"""Audit the entire isolated lock; allow only explicitly contained offline findings.

This does NOT alter or waive the application's existing dependency audit.
Known diskcache/filelock findings require an attacker-controlled local cache or
lock path. The worker creates a private empty 0700 temp root before SDK import,
then disables disk/memory caching. Provider evaluation uses only fixed synthetic
inputs and cache=False. No local filenames are accepted from examples/models.
See README for the residual risk and why upgrading filelock alone is incompatible
with LiteLLM's <4 dependency constraint. Every other/new finding fails this gate.
"""
import json
from pathlib import Path
import subprocess
import sys

CONTAINED = {
    ("diskcache", "5.6.3"): {"PYSEC-2026-2447"},
    ("filelock", "3.32.7"): {
        "CVE-2026-112940","CVE-2026-112913","CVE-2026-112907","CVE-2026-112938",
        "CVE-2026-112936","CVE-2026-112910","CVE-2026-112909","CVE-2026-112911",
        "CVE-2026-112939","CVE-2026-112915","CVE-2026-112935","CVE-2026-112912","CVE-2026-112908",
    },
}


def unexpected(report):
    return [(d["name"],d["version"],v["id"]) for d in report["dependencies"] for v in d["vulns"]
            if v["id"] not in CONTAINED.get((d["name"],d["version"]),set())]


def main():
    target=Path(sys.argv[1])
    lock=Path(__file__).with_name("requirements.lock")
    result=subprocess.run([sys.executable,"-m","pip_audit","--no-deps","--disable-pip","-r",str(lock),"--format","json","--output",str(target)],timeout=180)
    if result.returncode not in (0,1) or not target.is_file():
        raise SystemExit("dependency_audit_failed")
    report=json.loads(target.read_text())
    unknown=unexpected(report)
    if unknown:
        print(json.dumps({"unexpected_findings":unknown}))
        raise SystemExit(1)
    print(json.dumps({"status":"AUDITED_WITH_CONTAINED_OFFLINE_FINDINGS",
                      "contained_findings":sorted({v["id"] for d in report["dependencies"] for v in d["vulns"]}),
                      "application_dependency_change":False,"production_adoption":False}))

if __name__=="__main__":
    main()
