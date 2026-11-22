# Disposable signed deployed QA preflight

The merged registration #617 expected a manually supplied session token and
conversation. Run 44842344067 stopped at the unset repository opt-in before any
QA request. Current GitHub inspection found the existing `acceptance`
environment already holds the E2E Supabase URL, anon key, service-role key and
matching allowed URL. No credential needs to be copied into chat or another
GitHub environment.

This change reuses only those acceptance credentials. The existing real Auth
trigger creates a uniquely tagged user workspace, profile, membership, trial
billing row and environment. The harness signs in through Auth, verifies the
actor, inserts one empty owned conversation, and calls the unchanged deployed
GET probe at c10d8a764f67c428adc408d65429149e7686498f. The probe source checksum
remains 347761a26bc874a0d885b0a463797708661bcb6fac9cbf5fdc047e9dfeb4ae82.
The QA backend URL and acceptance Supabase project are hardcoded allowlists.
The unsigned deployment identity gate runs before any fixture creation.

Manual dispatch requires repository owner `cesarbohjr`, this repository, and
`confirm_disposable_fixture=true` (default false). This explicit per-run opt-in
replaces the absent repository toggle. Only `refs/heads/main` may
dispatch the credentialed preflight. The former implementation branch
`ci/eco001-disposable-signed-preflight`, all other branches and tags fail
closed. PR-triggered execution runs offline fixture contracts only and
receives no environment credentials. The existing `acceptance`
environment has no reviewer/branch protection; no protected-environment claim
is made and no protection or secret is changed by this implementation.

The deployed API receives GET requests only. Setup/teardown writes target only
this run's synthetic fixture in gravitre-acceptance. No external provider,
Stripe, Voice, worker, migration, or production deployment is invoked.
Tokens/passwords stay in process memory and upstream bodies/errors never enter
logs. The private mode-0600 recovery journal contains only synthetic identifiers
and a random fixture tag. It is never uploaded.

Cleanup globally signs out the new session, deletes only the verified tagged
workspace and actor, and queries persisted absence of the conversation,
membership, profile, org, billing and environment rows. It separately verifies
Auth user absence and that refresh fails. Deleting/revoking a user does not make
an existing JWT cryptographically invalid before expiry; the absence of the
membership/conversation fences state reads. An always-run recovery step retries
cleanup without converting a failed preflight into a pass. Evidence is retained
even when the probe fails; a PASS requires verified cleanup.

Runner loss/SIGKILL or an unacknowledged Auth create is an uncertain outcome,
never a clean PASS. Ordinary SIGTERM executes the finally cleanup. The scoped
private journal supports the same runner's recovery step; the public fixture
tag supports independent metadata-only readback and incident follow-up. Do not
perform broad deletion of preexisting synthetic accounts.

Full authenticated QA, provider-write/rollback acceptance and the original
43 findings remain independently gated. This bounded fixture check certifies
none of those findings by itself. PR #611 remains open and undeployed by this
change. The temporary standalone registration still retires when consolidated
QA12 is registered on main.
