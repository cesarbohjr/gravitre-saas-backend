/**
 * Phase 2.5 (Gravitre Intelligence redesign, 2026-09-11) — honest,
 * business-language status translation.
 *
 * ABSOLUTE RULE: a bare lifecycle status word ("TRAINED", "Deployed",
 * "Failed") is banned anywhere in the user-facing product without real,
 * immediate context in the same view. This module is a **display-layer
 * translation only** — it never invents a new technical state; every key
 * below is a real, existing status value already produced somewhere in
 * this codebase (see the Phase 2.5 inventory in
 * docs/delivery/gravitre-intelligence-redesign-phase0-proposal-2026-09-11.md).
 *
 * The brief's own 8-row table (Untrained/Training/Trained/Deployed/
 * Evaluating/Stale/Failed/Fine-tuning) is reproduced exactly. The
 * additional keys are honest extensions for the real states this app
 * actually has today (heuristic/data_gate/planned/disabled from the
 * built-in ML catalog; draft/validating/ready/archived from the custom
 * model registry; ok/not_available/insufficient_data from predictive ops).
 */

export type StatusTone = "ready" | "learning" | "attention" | "neutral" | "off"

export type StatusLanguageEntry = {
  /** Business-friendly phrase — never the bare technical word. */
  phrase: string
  /** One-line honest context: what it means and/or what to do next. */
  detail: string
  tone: StatusTone
}

const FALLBACK: StatusLanguageEntry = {
  phrase: "Status unknown",
  detail: "No status information has been returned yet.",
  tone: "neutral",
}

/**
 * Technical state -> business-friendly language. Keys are lower-cased,
 * underscore-separated real status strings already produced by:
 *  - backend/app/ml/model_catalog.py (get_org_model_status: runtime_status)
 *  - backend/app/ml/base.py (ModelStatus / MlModelStatus registry lifecycle)
 *  - backend/app/services/predictive_operations_engine.py (domain pack status)
 *  - backend/app/services/training_signal_service.py (readiness status)
 */
export const STATUS_LANGUAGE: Record<string, StatusLanguageEntry> = {
  // --- Brief's exact target table -----------------------------------
  untrained: {
    phrase: "Needs training",
    detail: "No training run has started yet — add data on Training to activate it.",
    tone: "neutral",
  },
  not_trained: {
    phrase: "Needs training",
    detail: "No training run has started yet — add data on Training to activate it.",
    tone: "neutral",
  },
  training: {
    phrase: "Learning from your data",
    detail: "A training run is in progress right now.",
    tone: "learning",
  },
  trained: {
    phrase: "Ready to use",
    detail: "A trained version is available for your org.",
    tone: "ready",
  },
  ready: {
    phrase: "Ready to use",
    detail: "A trained version is available and eligible for deployment.",
    tone: "ready",
  },
  deployed: {
    phrase: "Actively predicting",
    detail: "This model is live and serving real predictions.",
    tone: "ready",
  },
  evaluating: {
    phrase: "Checking performance",
    detail: "Validating this model's results before it's marked ready.",
    tone: "learning",
  },
  validating: {
    phrase: "Checking performance",
    detail: "Validating this model's results before it's marked ready.",
    tone: "learning",
  },
  stale: {
    phrase: "Needs updating",
    detail: "This model hasn't been refreshed with recent data in a while.",
    tone: "attention",
  },
  failed: {
    phrase: "Training needs attention",
    detail: "The last training run didn't complete successfully.",
    tone: "attention",
  },
  fine_tuning: {
    phrase: "Improving with new examples",
    detail: "Fine-tuning on newly reviewed examples is underway.",
    tone: "learning",
  },

  // --- Honest extensions for other real states in this codebase ------
  draft: {
    phrase: "Needs training",
    detail: "Registered, but no training run has started yet.",
    tone: "neutral",
  },
  archived: {
    phrase: "Archived",
    detail: "Kept for reference — not active and not receiving new data.",
    tone: "off",
  },
  heuristic: {
    phrase: "Estimating with rules",
    detail: "Using rule-based estimates while it builds toward full training on your org's data.",
    tone: "learning",
  },
  data_gate: {
    phrase: "Needs more data",
    detail: "Not enough verified examples yet to train reliably — a minimum quality gate, not a cap.",
    tone: "neutral",
  },
  insufficient_data: {
    phrase: "Needs more data",
    detail: "Not enough verified examples yet to measure or train this reliably.",
    tone: "neutral",
  },
  already_trained_recently: {
    phrase: "Recently trained",
    detail: "This model was trained recently — more data will still improve it further.",
    tone: "ready",
  },
  planned: {
    phrase: "Not built yet",
    detail: "On the platform roadmap — not trainable for your org today.",
    tone: "off",
  },
  disabled: {
    phrase: "Turned off",
    detail: "Disabled platform-wide (e.g. pending legal/consent review) — not available today.",
    tone: "off",
  },
  ok: {
    phrase: "Working normally",
    detail: "This prediction pack is producing results for your org.",
    tone: "ready",
  },
  not_available: {
    phrase: "Not available",
    detail: "This prediction isn't available for your org yet.",
    tone: "off",
  },
  unknown: FALLBACK,
}

/** Look up the honest, business-friendly language for a real technical status. */
export function describeStatus(status: string | null | undefined): StatusLanguageEntry {
  const key = String(status ?? "")
    .trim()
    .toLowerCase()
  if (!key) return FALLBACK
  const entry = STATUS_LANGUAGE[key]
  if (entry) return entry
  // Unknown-but-present status: never fabricate a phrase, just humanize the
  // real word we were given and say plainly that no honest mapping exists.
  return {
    phrase: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    detail: "No business-language mapping exists yet for this exact technical status.",
    tone: "neutral",
  }
}

export const TONE_BADGE_CLASS: Record<StatusTone, string> = {
  ready: "border-success/30 bg-success/10 text-success",
  learning: "border-info/30 bg-info/10 text-info",
  attention: "border-warning/30 bg-warning/10 text-warning",
  off: "border-border bg-muted text-muted-foreground",
  neutral: "border-border/70 bg-secondary/40 text-muted-foreground",
}
