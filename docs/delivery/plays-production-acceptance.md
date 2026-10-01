# Plays — production acceptance contract

Slice 6 closes the six-slice Plays implementation without creating a parallel runtime.

## Release gates

1. **Architecture:** Play execution delegates only to canonical workflows.
2. **Tenant isolation:** installation, run, outcome, impact, and evidence reads/writes remain org scoped.
3. **Governance:** Observe/Recommend never perform writes. Act with approval requires canonical workflow approval policy. Act within policy remains fail-closed until effective runtime action authorization is proven.
4. **Outcome truth:** workflow completion and provider acceptance are not business success. Only source-of-record VERIFIED SUCCESS with a measured metric delta enters verified impact.
5. **Traceability:** verified evidence can trace Play → installation/run → workflow run → approvals → source record.
6. **UX:** Plays is first-class beside Goals; setup, execution, results and evidence use existing Gravitre primitives.
7. **Regression:** full backend/web CI must remain green.
8. **Production proof:** authenticated production acceptance is GET-only and emits a JSON evidence artifact.

## Customer-data execution

The production acceptance workflow intentionally does **not** execute a Play against customer systems. Real execution can mutate external systems and must remain an explicit, authorized user action through the normal Play + workflow approval path.

A release is not allowed to claim recovered revenue, protected revenue, retention lift, or marketing lift from workflow completion alone.

## Demo standard

Use the same Play surfaces and runtime for demos. Example/demo records must be clearly identified as example data and must never be aggregated into verified customer impact. When real connectors and source records are available, the same Play can progress through readiness, governed execution, verification and Dashboard impact without switching to a separate demo engine.
