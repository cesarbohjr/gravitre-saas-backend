/**
 * Feature flag for Phase 2 of the "Gravitre AI Agent Workspace" redesign
 * (Helper bubble + Float window).
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part C6, phase row 2: "Mount + Float, behind a flag."
 *
 * Mechanism: follows the existing `NEXT_PUBLIC_*`-env-var convention already
 * used in `apps/web/lib/marketing-flags.ts` (`SHOW_RESEARCH_LOOKUPS_PRICING`).
 * That flag is opt-OUT (`!== "false"`, defaults to enabled). This one is
 * deliberately the opposite polarity — opt-IN (`=== "true"`, defaults to
 * disabled) — because Phase 2 must ship with zero visible change for every
 * existing user until explicitly turned on. No org/user allowlist mechanism
 * exists anywhere in this codebase today (confirmed via repo-wide grep for
 * `feature_flag` / `isFeatureEnabled` / `useFeatureFlag` before writing this
 * file); the `NEXT_PUBLIC_*` env-var convention is the only reusable pattern
 * that exists, so this reuses it rather than inventing a new mechanism.
 */
export const GRAVITRE_AI_FLOAT_ENABLED = process.env.NEXT_PUBLIC_AI_FLOAT_ENABLED === "true"
