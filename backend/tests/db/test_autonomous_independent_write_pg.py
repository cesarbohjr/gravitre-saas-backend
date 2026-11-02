"""Autonomous write ledger + independent process receiver acceptance.

Real PostgreSQL RPCs and real HTTP side effects, not fake ledger responses.
The test issues simulated dispatch decisions; it does not certify all live
provider adapters or the production ReAct call stack.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.db.pg_harness import PG_BIN, MIGRATIONS, pg_cluster, requires_pg
from tests.db.test_write_invoke_idempotency_pg import BOOTSTRAP_SQL, ORG_A, ORG_B, _claim, _finalize

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "native-workers"))
from broker_process_contract import IndependentFixture

pytestmark = requires_pg
AUDIT = Path(os.environ.get("AUTONOMOUS_WRITE_AUDIT_PATH", "/tmp/autonomous-write-audit"))
MIGRATION = MIGRATIONS / "20261016032018_write_invoke_idempotency.sql"
GRANTS = MIGRATIONS / "20261016032029_write_invoke_idempotency_grants.sql"


def _post(receiver, token):
    payload = json.dumps({"cap": token}).encode()
    request = urllib.request.Request(
        receiver.origin + "/write", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=7) as response:
        assert response.status == 204


def _post_child(origin, token):
    payload = json.dumps({"cap": token}).encode()
    request = urllib.request.Request(
        origin + "/write", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        assert response.status == 204


def _wait_child(stop):
    stop.wait(20)


def _expired(pg, key):
    pg.psql(f"""SET ROLE service_role;
UPDATE public.write_invoke_idempotency
SET lease_expires_at = now() - interval '1 minute'
WHERE org_id = '{ORG_A}' AND idempotency_key = '{key}';""")


def _evidence(case, receiver, expected, *, outcome):
    actual = receiver.writes
    AUDIT.mkdir(parents=True, exist_ok=True)
    payload = {
        "case": case,
        "receiver_pid": receiver.pid,
        "expected_committed_writes": expected,
        "observed_committed_writes": actual,
        "unauthorized_or_duplicate_writes": max(0, actual - expected),
        "ledger_outcome": outcome,
        "passed": actual == expected,
    }
    (AUDIT / (case + ".json")).write_text(json.dumps(payload, indent=2))
    assert actual == expected


def test_independent_receiver_and_pg_ledger_matched_cases(tmp_path):
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text(), GRANTS.read_text()) as pg:
        for case, expected in (
            ("denied_dispatch", 0),
            ("cross_tenant_denied", 0),
            ("completed_replay", 1),
            ("lost_ack", 1),
            ("crash_before_effect", 0),
            ("crash_after_effect", 1),
        ):
            token = "cap-" + case
            receiver = IndependentFixture(tmp_path / (case + ".sqlite3"), b"<h1>Acceptance</h1>", capability=token)
            key = "invoke:autonomous-" + case
            try:
                assert receiver.pid != os.getpid()
                if case in ("denied_dispatch", "cross_tenant_denied"):
                    # A blocked admission never receives a write capability.
                    assert receiver.writes == 0
                    if case == "cross_tenant_denied":
                        # Same key in another tenant has an independent ledger
                        # namespace and never authorizes tenant A's receiver.
                        assert _claim(pg, ORG_B, key)["outcome"] == "claimed"
                    _evidence(case, receiver, 0, outcome="no_authorized_dispatch")
                    continue

                claim = _claim(pg, ORG_A, key)
                assert claim["outcome"] == "claimed"
                if case == "completed_replay":
                    _post(receiver, token)
                    assert _finalize(pg, ORG_A, key, claim["claim_token"])["outcome"] == "finalized"
                    assert _claim(pg, ORG_A, key)["outcome"] == "replay"
                    _evidence(case, receiver, 1, outcome="replayed_without_provider_call")
                elif case == "crash_before_effect":
                    context = mp.get_context("spawn")
                    hold = context.Event()
                    child = context.Process(target=_wait_child, args=(hold,))
                    child.start()
                    assert child.pid is not None and child.is_alive()
                    child.kill()
                    child.join(timeout=5)
                    assert child.exitcode != 0
                    _expired(pg, key)
                    assert _claim(pg, ORG_A, key)["status"] == "uncertain"
                    _evidence(case, receiver, 0, outcome="killed_before_effect_uncertain")
                else:
                    # Receiver commits a real HTTP write before acknowledgement.
                    # A client timeout or worker death must never trigger retry.
                    receiver.hold = True
                    context = mp.get_context("spawn")
                    worker = context.Process(target=_post_child, args=(receiver.origin, token))
                    worker.start()
                    assert worker.pid is not None and worker.pid != receiver.pid
                    deadline = time.monotonic() + 5
                    while receiver.writes == 0 and time.monotonic() < deadline:
                        time.sleep(.04)
                    assert receiver.writes == 1, "provider-side effect not observed"
                    _expired(pg, key)
                    blocked = _claim(pg, ORG_A, key)
                    assert blocked["outcome"] == "blocked" and blocked["status"] == "uncertain"
                    if case == "crash_after_effect":
                        worker.kill()
                        worker.join(timeout=5)
                        assert worker.exitcode != 0
                    else:
                        receiver.hold = False
                        worker.join(timeout=5)
                        assert worker.exitcode == 0
                    _evidence(
                        case, receiver, 1,
                        outcome="killed_after_effect_uncertain" if case == "crash_after_effect"
                        else "lost_ack_uncertain",
                    )
            finally:
                receiver.hold = False
                receiver.close()

        # Restart PostgreSQL service over the same data directory. This is a
        # graceful service restart, not a power-loss durability simulation.
        pg.stop()
        opts = f"-k {pg.sock} -p {pg.port} -c listen_addresses='' -c fsync=off"
        subprocess.run(
            pg._cmd("pg_ctl", "-D", str(pg.data), "-o", opts, "-w",
                    "-l", str(pg.root / "restart.log"), "start"),
            check=True, capture_output=True,
        )
        for case in ("lost_ack", "crash_before_effect", "crash_after_effect"):
            key = "invoke:autonomous-" + case
            assert _claim(pg, ORG_A, key)["outcome"] == "blocked"
