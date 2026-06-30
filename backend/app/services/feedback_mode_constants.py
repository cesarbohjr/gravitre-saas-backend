"""Mode A/B feedback loop constants (STA-293 / STA-294)."""
from __future__ import annotations

FEEDBACK_MODE_A = "mode_a"
FEEDBACK_MODE_B = "mode_b"
ALLOWED_FEEDBACK_MODES = frozenset({FEEDBACK_MODE_A, FEEDBACK_MODE_B})

DEFAULT_MAX_SHIFT_PERCENT_PER_CYCLE = 15.0
DEFAULT_PACK_SLUG = ""
MARKETING_PACK_SLUG = "marketing-operations-pack"

MUTATION_DIMENSIONS = frozenset({"tone", "cadence", "content_type"})
POOR_OUTCOME_WIN_RATE = 0.35

AUDIT_MODE_B_ENABLED = "feedback.mode_b.enabled"
AUDIT_MODE_B_DISABLED = "feedback.mode_b.disabled"
AUDIT_MODE_B_MUTATION = "feedback.mode_b.mutation_applied"
AUDIT_MODE_B_ROLLBACK = "feedback.mode_b.rollback"
AUDIT_MODE_B_CAP_BLOCKED = "feedback.mode_b.cap_blocked"

EVENT_MUTATION_APPLIED = "mutation_applied"
EVENT_ROLLBACK = "rollback"
EVENT_CAP_BLOCKED = "cap_blocked"
EVENT_REPLAN_CYCLE = "replan_cycle"
EVENT_MODE_ENABLED = "mode_enabled"
EVENT_MODE_DISABLED = "mode_disabled"

TONE_OPTIONS = ("professional", "conversational", "bold", "empathetic")
CADENCE_OPTIONS = ("daily", "twice_weekly", "weekly", "biweekly")
CONTENT_TYPE_OPTIONS = ("blog", "social", "email", "mixed")
