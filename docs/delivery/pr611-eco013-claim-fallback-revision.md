# Pending-status claim and concurrent conversation edits

At dcfe492 the missing-function fallback reported a successful claim but
restored the original topic and revision 8 over an independent committed
update at revision 9. The retained SQL function preserved the new topic and
left the revision at 9. The two paths were tested through the service and
Supabase SDK with PostgREST 16.6 and disposable PostgreSQL 16.2. SQL readback
checked both the claim row and the separate tenant fixture.

The fallback now conditions its write on organization, conversation, pending
status and the observed revision. A successful fallback increments the revision.
After a conflict it reloads state and retries only while the validated pending
task and execution plan match. The retry count is bounded. For RPC claims only
a missing-function response allows the compatibility write. A negative RPC
result, a denial or an uncertain outcome cannot authorize a second attempt
through the table. The SQL function itself has no new revision behavior.

The new persisted regressions cover the SQL function, a harmless concurrent
topic update at the fallback boundary, and refusal after a changed draft or
execution plan. Independent readback after a successful fallback finds the
updated topic, the claim and revision 10. These are isolated tests, optional
without local binaries. The mandatory QA12 suites retain counts of 20, 6 and 8.
Production occurrence, live approval timing and provider acceptance remain open.
