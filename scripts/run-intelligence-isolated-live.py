#!/usr/bin/env python3
"""Authenticated isolated-org intelligence lifecycle run; fail closed.

Drives one synthetic internal assignment through the real product path, in the
smoke org only, with the short-lived smoke-org session (scripts/mint_smoke_org_session.py):

1. Chat asks Gravitre to stage an internal assignment carrying a unique trace.
2. The staged action is read back from the conversation state
   (GET /api/assistant/conversation/{id}/state): type ``create_assignment``,
   ``awaiting_confirm``, the brief carries the trace, and no assignment exists yet.
3. Negative controls: the same approval from another org and on another
   conversation is refused and creates nothing.
4. Approval (POST .../execute) creates exactly one assignment; a second approval
   replays and creates none.
5. The assignment is read back until it finishes, then its outcome run and that
   run's ``execution.outcome_finalized`` event are read back through
   GET /api/admin/intelligence/outcomes/trace; learning counts only when the
   outcome-learning handler took that event.

Never approves on model text: approval waits on the state readback. Never sends
to external providers. Business-metric impact and customer sentiment are not
measured here (a synthetic internal assignment has no business metric); the
report says so instead of passing them.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TEST_ORG = "f07e57c0-1501-4000-8000-c04e57a00001"
API_ROOT = "https://api.gravitre.app"
LEARNING_HANDLER = "outcome_learning.record_run_outcome"
JOB_TERMINAL = frozenset({"completed", "failed", "cancelled"})
NOT_COVERED = ("business_metric_impact", "customer_sentiment_capture", "changed_draft_reapproval")
PROMPT = (
    "Controlled synthetic intelligence acceptance {trace}. Customer says: "
    '"I am extremely frustrated. Onboarding is two weeks late. Unless we have a '
    'recovery plan by Friday we will cancel our renewal." Renewal is in 30 days '
    "with two unresolved onboarding issues. Stage an internal Gravitre assignment "
    'titled "[E2E TEST] {trace} recovery plan" for my approval: draft a recovery '
    "plan as a note inside Gravitre only. No email, Slack, external providers or "
    "customer contact. Do not run it until I approve."
)


class ProbeError(Exception):
    pass


Http = Callable[..., tuple[int, Any]]


def http_request(method: str, url: str, token: str, org: str, payload: Any = None,
                 *, stream: bool = False, timeout: float = 120) -> tuple[int, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "X-Org-Id": org,
        "X-Environment": "production",
        "Accept": "text/event-stream" if stream else "application/json",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read(4_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read(4000).decode("utf-8", "replace")
    if stream:
        return status, raw
    try:
        return status, json.loads(raw) if raw.strip() else {}
    except ValueError:
        return status, {"_non_json": True}


class Run:
    def __init__(self, http: Http, *, base: str, token: str, org: str,
                 sleep: Callable[[float], None] = time.sleep,
                 job_timeout: float = 600, learning_timeout: float = 240) -> None:
        self.http, self.base, self.token, self.org = http, base.rstrip("/"), token, org
        self.sleep, self.job_timeout, self.learning_timeout = sleep, job_timeout, learning_timeout
        self.trace = "GV-INT-E2E-" + uuid.uuid4().hex[:12]
        self.report: dict[str, Any] = {
            "trace_id": self.trace, "org_id": org, "synthetic_only": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "scope": "assignment lifecycle: stage, approve once, execute, outcome, learning delivery",
            "not_covered": list(NOT_COVERED), "checks": [], "verdict": "FAIL",
        }

    def check(self, name: str, ok: bool, detail: Any = "") -> None:
        self.report["checks"].append({"name": name, "passed": bool(ok), "detail": detail})
        if not ok:
            raise ProbeError(name)

    def call(self, method: str, path: str, payload: Any = None, *, org: str | None = None,
             stream: bool = False) -> tuple[int, Any]:
        return self.http(method, self.base + path, self.token, org or self.org, payload, stream=stream)

    def job_ids(self) -> set[str]:
        status, body = self.call("GET", "/api/agent-jobs?limit=100")
        if status != 200 or not isinstance(body, dict):
            raise ProbeError(f"agent_jobs_list_http_{status}")
        return {str(j.get("jobId")) for j in body.get("jobs") or [] if j.get("jobId")}

    def state(self, conversation_id: str) -> dict[str, Any]:
        status, body = self.call("GET", f"/api/assistant/conversation/{conversation_id}/state")
        if status != 200 or not isinstance(body, dict):
            raise ProbeError(f"conversation_state_http_{status}")
        task_state = body.get("task_state")
        return task_state if isinstance(task_state, dict) else {}

    def approve(self, conversation_id: str, *, org: str | None = None) -> tuple[int, Any]:
        return self.call("POST", f"/api/assistant/conversation/{conversation_id}/execute",
                         {"confirm": True}, org=org)

    def execute(self) -> dict[str, Any]:
        trace = self.trace
        status, conv = self.call("POST", "/api/conversations", {"title": f"[E2E TEST] {trace}"})
        conversation_id = str((conv or {}).get("id") or "") if isinstance(conv, dict) else ""
        self.check("conversation_created", status in (200, 201) and bool(conversation_id), status)
        self.report["conversation_id"] = conversation_id

        before = self.job_ids()
        message = PROMPT.format(trace=trace)
        status, stream = self.call("POST", "/api/assistant/chat", {
            "org_id": self.org, "conversation_id": conversation_id, "mode": "standard",
            "messages": [{"id": str(uuid.uuid4()), "role": "user",
                          "parts": [{"type": "text", "text": message}]}],
        }, stream=True)
        self.check("chat_stream_returned", status == 200 and bool(str(stream).strip()), status)
        self.report["chat_bytes"] = len(str(stream))

        # Approval waits on the persisted staged action, never on model text.
        pending = self.state(conversation_id).get("pending_task")
        pending = pending if isinstance(pending, dict) else {}
        params = pending.get("params") if isinstance(pending.get("params"), dict) else {}
        self.report["staged"] = {"type": pending.get("type"), "status": pending.get("status")}
        self.check("staged_action_is_internal_assignment", pending.get("type") == "create_assignment",
                   pending.get("type"))
        self.check("staged_action_awaits_approval", pending.get("status") == "awaiting_confirm",
                   pending.get("status"))
        self.check("staged_brief_carries_trace", trace in str(params.get("assignment_task") or ""))
        self.check("nothing_ran_before_approval", self.job_ids() - before == set())

        status, _ = self.approve(conversation_id, org=str(uuid.uuid4()))
        self.check("other_org_approval_refused", status in (401, 403, 404), status)
        status, _ = self.approve(str(uuid.uuid4()))
        self.check("other_conversation_approval_refused", status in (403, 404), status)
        self.check("refused_approvals_created_nothing", self.job_ids() - before == set())
        self.check("still_awaiting_after_refusals",
                   (self.state(conversation_id).get("pending_task") or {}).get("status") == "awaiting_confirm")

        status, body = self.approve(conversation_id)
        result = (body or {}).get("execution_result") if isinstance(body, dict) else None
        result = result if isinstance(result, dict) else {}
        job_id = str(result.get("entity_id") or "")
        self.check("approval_executed", status == 200 and bool((body or {}).get("success")), status)
        self.check("approval_created_assignment", result.get("entity_type") == "agent_job" and bool(job_id),
                   result.get("entity_type"))
        self.report["job_id"] = job_id
        created = self.job_ids() - before
        self.check("exactly_one_assignment_created", created == {job_id}, len(created))

        status, body = self.approve(conversation_id)
        replay = (body or {}).get("execution_result") if isinstance(body, dict) else None
        structured = (replay or {}).get("structured") if isinstance(replay, dict) else None
        self.check("duplicate_approval_replayed", status == 200 and bool((structured or {}).get("replayed")), status)
        self.check("duplicate_approval_created_nothing", self.job_ids() - before == {job_id})

        job = self.wait_for_job(job_id)
        self.report["job_status"] = job.get("status")
        self.check("assignment_completed", job.get("status") == "completed", job.get("status"))

        outcome = self.wait_for_learning(job_id)
        runs = outcome.get("runs") or []
        events = outcome.get("events") or []
        self.report["outcome"] = {
            "run_ids": [r.get("id") for r in runs],
            "run_statuses": [r.get("status") for r in runs],
            "events": [{k: e.get(k) for k in ("event_id", "run_id", "status", "learning_delivered")}
                       for e in events],
        }
        self.check("one_outcome_run", len(runs) == 1, len(runs))
        self.check("outcome_run_completed", runs[0].get("status") == "completed", runs[0].get("status"))
        run_id = str(runs[0].get("id") or "")
        self.check("learning_received_this_outcome",
                   any(e.get("run_id") == run_id and e.get("learning_delivered") for e in events))

        status, delivery = self.call("GET", "/api/admin/intelligence/outcomes/delivery")
        delivery = delivery if isinstance(delivery, dict) else {}
        self.check("learning_delivery_healthy",
                   status == 200 and delivery.get("status") in ("idle", "queued") and not delivery.get("blockers"),
                   delivery.get("blockers") or delivery.get("status"))
        self.report["verdict"] = "PASS"
        return self.report

    def wait_for_job(self, job_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.job_timeout
        while True:
            status, job = self.call("GET", f"/api/agent-jobs/{job_id}")
            if status != 200 or not isinstance(job, dict):
                raise ProbeError(f"assignment_readback_http_{status}")
            if job.get("status") in JOB_TERMINAL or job.get("status") == "paused":
                return job
            if time.monotonic() >= deadline:
                self.check("assignment_finished_in_time", False, job.get("status"))
            self.sleep(10)

    def wait_for_learning(self, job_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.learning_timeout
        while True:
            status, trace = self.call("GET", f"/api/admin/intelligence/outcomes/trace?jobId={job_id}")
            if status != 200 or not isinstance(trace, dict):
                raise ProbeError(f"outcome_trace_http_{status}")
            if any(e.get("learning_delivered") for e in trace.get("events") or []):
                return trace
            if time.monotonic() >= deadline:
                return trace
            self.sleep(15)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-base", default=API_ROOT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--allow-synthetic-write", action="store_true")
    args = ap.parse_args()
    org = os.environ.get("PLATFORM_LIVE_ORG_ID", "").strip()
    token = os.environ.get("PLATFORM_LIVE_BEARER_TOKEN", "").strip()
    if org != TEST_ORG:
        raise SystemExit("REFUSED: only the isolated smoke org is allowed")
    if args.api_base.rstrip("/") != API_ROOT:
        raise SystemExit("REFUSED: unexpected API target")
    if os.environ.get("PLATFORM_LIVE_AUTH_MODE") != "smoke_org_short_lived" or not token:
        raise SystemExit("REFUSED: needs the short-lived smoke-org session")
    if not args.allow_synthetic_write:
        raise SystemExit("REFUSED: pass --allow-synthetic-write")
    run = Run(http_request, base=args.api_base, token=token, org=org)
    try:
        run.execute()
    except (ProbeError, urllib.error.URLError, TimeoutError) as exc:
        run.report["blocker"] = str(exc)[:160]
    finally:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(run.report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: run.report.get(k) for k in ("verdict", "trace_id", "blocker", "not_covered")}))
    return 0 if run.report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
