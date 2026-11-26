# Conversation channel preference and concurrent state writes

On 637ae2a the channel override in unified_turn_pending_live.py calls
ConversationStateService.apply_task_state_change_sync. The process lock
serializes local calls. An independent committed writer can change the row
after the initial read. The synchronous save previously replaced the whole
JSON column using only organization and conversation predicates.

A disposable PostgreSQL 16.2 / PostgREST 16.6 test starts at revision 8,
commits a separate context change at revision 9 before the HTTP PATCH, and
reads the result independently over SQL. The baseline returned success and
restored the original topic at revision 8. With a revision predicate and
bounded retries, the newer topic and the requested preference coexist at
revision 10. The cancellation check runs before each write. A missing revision
uses the existing null-revision convention. This is a synthetic context race.
Deployed occurrence, approval-claim races and provider behavior remain open.

The new regression, existing cancellation fence suite and eight persisted plan
contracts passed locally (32 tests). The existing independent QA12 artifact
counts remain 20, six and eight. The new regression requires local binaries.
