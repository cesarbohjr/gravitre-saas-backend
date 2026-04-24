"""BE-11: Workflow schema version, size limits, allowed step types."""
# Supported definition schema version
SCHEMA_VERSION = "2025.1"

# Size limits (enforced in application)
DEFINITION_MAX_BYTES = 256 * 1024   # 256 KiB
PARAMS_MAX_BYTES = 64 * 1024        # 64 KiB
MAX_STEPS = 50
OUTPUT_SNAPSHOT_MAX_BYTES = 128 * 1024  # 128 KiB per step

# Allowed step types for dry-run (connectors simulated only until implemented)
ALLOWED_STEP_TYPES = frozenset({
    "rag_retrieve",
    "transform",
    "condition",
    "noop",
    "slack_post_message",
    "email_send",
    "webhook_post",
})

RUN_TYPE_DRY_RUN = "dry_run"
RUN_TYPE_EXECUTE = "execute"
RUN_STATUS_RUNNING = "running"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_FAILED = "failed"
RUN_STATUS_PENDING_APPROVAL = "pending_approval"
RUN_STATUS_CANCELLED = "cancelled"

# BE-20 + IN-10/11/12: execute-allowed (approval-gated external actions)
EXECUTE_ALLOWED_STEP_TYPES = frozenset({"rag_retrieve", "noop", "slack_post_message", "email_send", "webhook_post"})

# BE-20: closed role set for approver_roles
ALLOWED_ROLES = frozenset({"admin", "member"})
SAFE_DEFAULT_APPROVER_ROLES = ["admin"]
SAFE_DEFAULT_REQUIRED_APPROVALS = 1

STEP_STATUS_PENDING = "pending"
STEP_STATUS_RUNNING = "running"
STEP_STATUS_COMPLETED = "completed"
STEP_STATUS_FAILED = "failed"
STEP_STATUS_SKIPPED = "skipped"

AUDIT_ACTION_DRY_RUN_STARTED = "workflow.dry_run.started"
# BE-20 execute audit actions
AUDIT_ACTION_EXECUTE_CREATED = "workflow.execute.created"
AUDIT_ACTION_EXECUTE_PENDING_APPROVAL = "workflow.execute.pending_approval"
AUDIT_ACTION_EXECUTE_APPROVAL_RECORDED = "workflow.execute.approval_recorded"
AUDIT_ACTION_EXECUTE_APPROVED = "workflow.execute.approved"
AUDIT_ACTION_EXECUTE_REJECTED = "workflow.execute.rejected"
AUDIT_ACTION_EXECUTE_STARTED = "workflow.execute.started"
AUDIT_ACTION_EXECUTE_STEP_COMPLETED = "workflow.execute.step_completed"
AUDIT_ACTION_EXECUTE_STEP_FAILED = "workflow.execute.step_failed"
AUDIT_ACTION_EXECUTE_COMPLETED = "workflow.execute.completed"
AUDIT_ACTION_EXECUTE_FAILED = "workflow.execute.failed"
AUDIT_ACTION_EXECUTE_CANCELLED = "workflow.execute.cancelled"
AUDIT_ACTION_DRY_RUN_STEP_COMPLETED = "workflow.dry_run.step_completed"
AUDIT_ACTION_DRY_RUN_STEP_FAILED = "workflow.dry_run.step_failed"
AUDIT_ACTION_DRY_RUN_COMPLETED = "workflow.dry_run.completed"
RESOURCE_TYPE_WORKFLOW_RUN = "workflow_run"

ERROR_CODE_VALIDATION = "validation"
ERROR_CODE_RAG_UNAVAILABLE = "rag_unavailable"
ERROR_CODE_STEP_FAILED = "step_failed"
ERROR_CODE_SLACK_FAILED = "slack_failed"
ERROR_CODE_EMAIL_FAILED = "email_failed"
ERROR_CODE_WEBHOOK_FAILED = "webhook_failed"
ERROR_CODE_RATE_LIMITED = "rate_limited"