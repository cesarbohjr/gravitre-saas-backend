/**
 * Feature flag for the Gravitre AI Agent Workspace redesign (Helper + Float +
 * Expanded + Fullscreen + mobile sheet).
 *
 * Phase 5 (2026-09-09): default ON for rollout. Kill-switch:
 * `NEXT_PUBLIC_AI_FLOAT_ENABLED=false`.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part C6 / Reassessment Phase 5.
 */
export const GRAVITRE_AI_FLOAT_ENABLED = process.env.NEXT_PUBLIC_AI_FLOAT_ENABLED !== "false"
