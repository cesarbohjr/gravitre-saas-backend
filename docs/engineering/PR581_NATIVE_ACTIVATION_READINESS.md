# PR581 native activation readiness

## Current source checkpoint

The private durable broker, pinned SDK engine images, constrained model/network gateway, canonical approved tool operations and acknowledged Langfuse outbox are now implemented in source. See [implementation and release-stage configuration](PR581_NATIVE_RUNTIME_IMPLEMENTATION.md). Offline authorization, queue, delivery and failure contracts pass; real image/runtime certification, exact-head full CI and combined compatibility remain required. No worker or telemetry has been activated.

The remainder below records the earlier environment inventory and historical missing-code checkpoint; its NOT IMPLEMENTED labels are superseded by the source checkpoint above.

## Historical verified checkpoint

The Operations and software Engineering/IT implementations are source changes, not native worker activation. The existing `native_agent_adapters.py` still creates review-only plans and performs explicit-per-run, metrics-only Langfuse submission. It must not be reported as an operational sandbox worker, browser runtime or acknowledged delivery queue.

A read-only Railway inventory found only the backend and Redis in the backend project's production environment, with no staged changes. The backend service's variable-name inventory contained no OpenHands, Browser Use, Langfuse or native-worker configuration names. This is evidence about this configured Railway environment, not a claim that no unrelated external account exists. No variable values or credentials were retrieved. No service, environment, secret, worker or telemetry setting was changed.

## API and isolation review

Reviewed the previously pinned upstream READMEs for OpenHands Canvas (`6354932e87f99e1583f482f2cea49d6d573443e0`), Browser Use (`2cc71890e65056b67fdb29d98bb407749c15bb08`) and Langfuse Python (`b483bd06ae7953e16f1f50d5a0316de3bb2aaaec`). Also inspected the canonical OpenHands software-agent SDK at `47bbc5e8392c4c75b7f77a1da38bed4a9f53d6a5` and its DockerWorkspace/remote-conversation example. This audit does not add or activate an SDK dependency.

- OpenHands Canvas is not the canonical Python execution SDK. A local Conversation with terminal/file tools has host access; it is not an acceptable substitute for a tenant-isolated, budgeted workspace.
- Browser Use's allowed-domain and stop hooks do not by themselves prove redirect/subresource/network isolation or prevent a consequential authenticated browser action. A worker must enforce those boundaries and approvals outside model instructions.
- Langfuse SDK submission/flush is not durable remote acknowledgement. Delivery requires an idempotent queue, bounded retries, scoped acknowledgement verification and consent/deletion enforcement. No prompt, transcript, source record, credential or raw tenant identity may enter that queue/export.

## Outstanding engineering

1. Implement the configured OpenHands worker, sandbox provisioning and destruction, tenant-specific credential brokerage, cancellation/time/cost limits, immutable action provenance and review-before-apply path.
2. Implement the ephemeral Browser Use worker/session lifecycle with independently enforced navigation/redirect/subresource/egress rules, secret isolation, tenant separation and per-action approvals.
3. Implement Langfuse's durable metrics-only outbox, idempotent delivery, bounded retry, acknowledgement/failure observability and consent/retention/deletion lifecycle.
4. Integrate these execution paths with canonical tool IAM, grant checks, current approvals, interruption/revocation and shared text/voice planning. Expose truthful configured/degraded/unavailable status without inventing a connector or granting tools.
5. Add isolated offline integration/failure tests; run final full CI and combined PR587 compatibility. Provision/activate infrastructure only through the coordinated, authorized deployment; execute live/provider and production acceptance afterward.

## Status

**NOT IMPLEMENTED / NOT ACTIVATED / NOT PRODUCTION-CERTIFIED.** The missing worker/runtime and delivery paths remain an explicit PR581 engineering blocker. Missing production configuration is not a reason to silently substitute an unsandboxed local SDK or mark this gate complete. PR581 remains draft and unmerged; PR587 and production deployment are unchanged.
