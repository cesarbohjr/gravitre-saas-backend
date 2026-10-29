"""One tool/schema contract consumed by the planner and canonical action catalog."""
def schema(properties,required=()):
    return {'type':'object','properties':properties,'required':list(required),'additionalProperties':False}
RUN={'run_id':{'type':'string','minLength':1,'maxLength':200}}
JOB={**RUN,'job_id':{'type':'string','format':'uuid'}}
TASK={'task':{'type':'string','minLength':1,'maxLength':8000}}
DEFINITIONS={
 'run_openhands':('Use when the user approves a bounded software task in a configured isolated workspace. Returns a draft for review; never applies a patch or publishes. Requires an explicit native grant and approval.',schema({**TASK,'files':{'type':'object','maxProperties':20,'additionalProperties':{'type':'string','maxLength':16000}}},('task',))),
 'run_browser_use':('Use when the user approves a governed browser task on explicit HTTPS hosts. Each consequential action waits for an exact human approval. No existing browser profile is reused.',schema({**TASK,'allowed_hosts':{'type':'array','minItems':1,'maxItems':10,'items':{'type':'string','maxLength':253}}},('task','allowed_hosts'))),
 'native_job_status':('Use when you need to read the current scoped native job status, review artifacts and pending exact browser action approvals. Submission is not completion.',schema(JOB,('job_id','run_id'))),
 'cancel_native_job':('Use when the user wants to cancel this actor’s native job and fence further worker actions.',schema(JOB,('job_id','run_id'))),
 'approve_native_action':('Use when a human must approve or refuse one exact pending browser action after human review. The request id, digest and page fingerprint must remain unchanged.',schema({**JOB,'request_id':{'type':'string','format':'uuid'},'digest':{'type':'string','pattern':'^[0-9a-f]{64}$'},'approved':{'type':'boolean'}},('job_id','run_id','request_id','digest','approved'))),
 'export_evaluation_metrics':('Use when the user explicitly opts in this run to delivery of the existing evaluation receipt’s allowlisted counts/timing only. No prompts, responses or raw identities are sent. Delivery requires remote verification.',schema({**RUN,'receipt_id':{'type':'string','format':'uuid'}},('run_id','receipt_id'))),
 'withdraw_evaluation_metrics':('Use when the user wants to withdraw this run’s metrics consent and request verified remote deletion. Report deletion as pending until confirmed.',schema(RUN,('run_id',))),
}
