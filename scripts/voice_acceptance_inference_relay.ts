// Temporary test-only Anthropic relay. Real provider credentials stay in Railway.
// Only this repository's owner-triggered PR587 acceptance job can authenticate.
import { createRemoteJWKSet, jwtVerify } from "jose@6.1.0";

const issuer = "https://token.actions.githubusercontent.com";
const audience = "gravitre-voice-acceptance";
const jwks = createRemoteJWKSet(new URL(`${issuer}/.well-known/jwks`));

export function allowedClaims(claims) {
  return claims.repository_id === "1219502745" &&
    claims.repository === "cesarbohjr/gravitre-saas-backend" &&
    claims.actor_id === "108694295" &&
    claims.sub === "repo:cesarbohjr/gravitre-saas-backend:environment:acceptance" &&
    claims.event_name === "pull_request" && claims.ref === "refs/pull/587/merge" &&
    claims.head_ref === "feat/phase2-dialogue-intelligence" &&
    claims.workflow_ref === "cesarbohjr/gravitre-saas-backend/.github/workflows/voice-gates-2-3.yml@refs/pull/587/merge";
}

export function makeHandler({env, verify, upstream = fetch, now = () => Date.now()}) {
  let accepted = 0;
  let active = 0;
  const error = (status, message) => Response.json({error: {type: "acceptance_relay_error", message}}, {status});
  return async function handle(request) {
    const url = new URL(request.url);
    const expires = Number(env.ACCEPTANCE_EXPIRES_AT || "0");
    if (!Number.isFinite(expires) || now() >= expires) return error(410, "Acceptance relay expired");
    if (url.pathname === "/health" && request.method === "GET") {
      return Response.json({scope: "pr587-acceptance-only", provider_configured: Boolean(env.ANTHROPIC_API_KEY), expires_at: expires});
    }
    if (request.method !== "POST" || url.pathname !== "/v1/messages" || url.search) return error(404, "Unsupported acceptance endpoint");
    const proof = request.headers.get("x-api-key") || "";
    let claims;
    try { claims = await verify(proof); } catch { return error(401, "Valid GitHub OIDC proof required"); }
    if (!allowedClaims(claims)) return error(403, "GitHub acceptance identity refused");
    if (!env.ANTHROPIC_API_KEY) return error(503, "Acceptance provider unavailable");
    if (active >= 2 || accepted >= 100) return error(429, "Acceptance trial bound reached");
    const reader = request.body?.getReader();
    if (!reader) return error(400, "Body required");
    const chunks = []; let size = 0;
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 512000) { await reader.cancel(); return error(413, "Acceptance input bound exceeded"); }
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
    let body;
    try { body = JSON.parse(new TextDecoder().decode(bytes)); } catch { return error(400, "Invalid JSON"); }
    if (!body || !["claude-sonnet-4-6", "claude-haiku-4-5-20251001"].includes(body.model) ||
        !Array.isArray(body.messages) || body.messages.length > 40 ||
        !Number.isInteger(body.max_tokens) || body.max_tokens < 1 || body.max_tokens > 4096) {
      return error(400, "Acceptance model or request bound refused");
    }
    // Recheck after body parsing so simultaneous requests cannot oversubscribe.
    if (active >= 2 || accepted >= 100) return error(429, "Acceptance trial bound reached");
    accepted++; active++;
    let handedOff = false; let released = false;
    const release = () => { if (!released) { released = true; active--; } };
    try {
      const response = await upstream("https://api.anthropic.com/v1/messages", {
        method: "POST", headers: {"content-type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": env.ANTHROPIC_API_KEY},
        body: JSON.stringify(body), signal: AbortSignal.timeout(90000), redirect: "error",
      });
      if (!response.ok) { await response.body?.cancel(); return error(response.status, `Provider returned HTTP ${response.status}`); }
      const headers = new Headers({"content-type": response.headers.get("content-type") || "application/json", "cache-control": "no-store"});
      if (response.headers.get("request-id")) headers.set("request-id", response.headers.get("request-id"));
      const reader = response.body?.getReader();
      if (!reader) return new Response(null, {status: response.status, headers});
      const bodyStream = new ReadableStream({
        async pull(controller) {
          try {
            const {done, value} = await reader.read();
            if (done) { release(); controller.close(); } else controller.enqueue(value);
          } catch (error) { release(); controller.error(error); }
        },
        async cancel(reason) { try { await reader.cancel(reason); } finally { release(); } },
      });
      handedOff = true;
      return new Response(bodyStream, {status: response.status, headers});
    } catch { return error(502, "Acceptance upstream request failed"); }
    finally { if (!handedOff) release(); }
  };
}

const handler = makeHandler({env: Bun.env, verify: async (proof) => {
  const {payload} = await jwtVerify(proof, jwks, {issuer, audience, algorithms: ["RS256"]});
  return payload;
}});
export default {port: Number(Bun.env.PORT || "3000"), fetch: handler};
