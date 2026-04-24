# Phase 7: Execution Sandboxing Plan (Design + Stub Only)

## Current Architectural Limitation
- Workflow execution runs inline with no explicit time or memory bounds.
- No abstraction layer to enforce sandboxed execution.

## Target Architecture
- Define an execution interface that can enforce limits (time, memory, I/O).
- Allow future sandbox implementations without changing workflow logic.

## Minimal Implementation Plan
- Document the required interface and constraints.
- Defer implementation (no runtime changes in Phase 7).

## Required Migrations
- None.

## Integration Changes
- None (design-only stub).

## Risks
- Without enforcement, long-running or expensive steps remain possible.

## Future Scaling Notes
- Introduce a sandbox executor (local or remote) with configurable limits.
- Add per-step timeouts and failure modes for policy enforcement.
