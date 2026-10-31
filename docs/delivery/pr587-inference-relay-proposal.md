# Isolated acceptance inference access — deployment pending approval

The acceptance GitHub environment has Deepgram/ElevenLabs credentials and a
dedicated Supabase project, but neither tested inference credential name is set.
Railway has Anthropic configured; the connected API exposes its name but not its
value. This proposal does not copy or expose the provider key.

The proposed `scripts/voice_acceptance_inference_relay.ts` is a separate Railway
Function, not a change to the production backend. It would run in the existing
Railway production environment namespace, reference the backend Anthropic key,
and expose a public HTTP endpoint protected by GitHub OIDC authentication.

The implemented restrictions require the exact repository ID, repository owner
actor, PR587 ref/head, acceptance environment subject and voice-gates workflow.
JWT verification uses pinned jose 6.1.0, GitHub's issuer/JWKS, RS256 and a dedicated
audience. Only Anthropic messages are forwarded; no admin, key or arbitrary URL
proxy is provided. The response never returns the provider credential. Input,
model, output-token, concurrency and per-process request-count bounds apply.
An absolute expiration must be configured or every request is refused. The
request count is process-local, not a durable account spending cap.

Five local policy tests pass, covering exact claims, expiry, invalid identities,
endpoint/token bounds, and fixed upstream/key injection. This is not a live
deployment or cryptographic integration certification. A successful GitHub OIDC
request and anonymous-denial check are required before inference trials.

Automatic approval review rejected deployment in the production environment as
outside the isolated-testing authorization. No Function was deployed. Do not
deploy or route around that rejection without explicit approval.

Safer alternative: configure a dedicated `ACCEPTANCE_ANTHROPIC_API_KEY` (or
`ACCEPTANCE_OPENAI_API_KEY`) in GitHub's `acceptance` environment. This avoids
creating any production-environment relay and is already supported by the gate.
