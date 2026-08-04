import { notFound } from "next/navigation"

import { SHOT_FIXTURES } from "@/lib/e2e-shot-fixtures"

/**
 * Screenshot harness for product surfaces.
 *
 * Renders the real pages, but swaps the network layer for fixtures so the
 * surfaces can be captured without a live backend, a Supabase session, or any
 * customer data. Gated the same way as the existing /e2e/execution-result
 * harness: 404 unless the E2E flag is on.
 *
 * The patch is emitted as a blocking inline script so it runs during HTML
 * parse — before any client module executes. Installing it from a client
 * component would be too late: AuthProvider's effect can fire first, and the
 * real fetch would escape to Supabase.
 */
export default function ShotsLayout({ children }: { children: React.ReactNode }) {
  // Never reachable in production. Unlike /e2e/execution-result, this also
  // opens in local dev: capturing marketing screenshots means running a normal
  // dev server, not the Playwright one that sets PLAYWRIGHT_E2E.
  const allowed =
    process.env.NODE_ENV !== "production" ||
    process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E === "1" ||
    process.env.PLAYWRIGHT_E2E === "1"

  if (!allowed) notFound()

  // Derived server-side so the cookie name matches whatever project the dev
  // server points at, rather than being hardcoded to one ref.
  const supabaseUrl =
    process.env.NEXT_PUBLIC_SUPABASE_URL ??
    process.env.NEXT_PUBLIC_gravitre_SUPABASE_URL ??
    ""
  const projectRef = supabaseUrl.replace(/^https?:\/\//, "").split(".")[0]

  const bootstrap = `
(function () {
  var F = ${JSON.stringify(SHOT_FIXTURES)};
  var REF = ${JSON.stringify(projectRef)};
  var realFetch = window.fetch.bind(window);

  // @supabase/ssr's browser client reads its session from a cookie, so a
  // fetch-level patch alone still leaves the app logged out and rendering the
  // sign-in screen. Seed a syntactically valid, far-future session; the token
  // is never verified because /auth/v1/user is intercepted below.
  function seedSession() {
    if (!REF) return;
    var now = Math.floor(Date.now() / 1000);
    var b64 = function (o) {
      return btoa(JSON.stringify(o)).replace(/\\+/g, "-").replace(/\\//g, "_").replace(/=+$/, "");
    };
    var jwt =
      b64({ alg: "HS256", typ: "JWT" }) + "." +
      b64({
        sub: F.__supabaseUser.id,
        email: F.__supabaseUser.email,
        role: "authenticated",
        aud: "authenticated",
        iat: now,
        exp: now + 60 * 60 * 24,
      }) + ".shot";

    var session = {
      access_token: jwt,
      refresh_token: "shot-refresh",
      token_type: "bearer",
      expires_in: 60 * 60 * 24,
      expires_at: now + 60 * 60 * 24,
      user: F.__supabaseUser,
    };

    var value = "base64-" + btoa(JSON.stringify(session));
    document.cookie =
      "sb-" + REF + "-auth-token=" + encodeURIComponent(value) + "; path=/; max-age=86400; SameSite=Lax";
  }
  seedSession();

  function json(body, status) {
    return new Response(JSON.stringify(body), {
      status: status || 200,
      headers: { "content-type": "application/json" },
    });
  }

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : (input && input.url) || String(input);

    // Supabase auth: hand back a fixed signed-in user so AuthProvider resolves
    // instead of hanging on a network call that would 401 here.
    if (url.indexOf("/auth/v1/user") !== -1) {
      return Promise.resolve(json(F.__supabaseUser));
    }
    // A refresh returning {} makes supabase-js treat the session as dead and
    // sign the user out mid-capture, so echo a valid session back.
    if (url.indexOf("/auth/v1/token") !== -1) {
      var now = Math.floor(Date.now() / 1000);
      return Promise.resolve(
        json({
          access_token: "shot",
          refresh_token: "shot-refresh",
          token_type: "bearer",
          expires_in: 86400,
          expires_at: now + 86400,
          user: F.__supabaseUser,
        })
      );
    }
    if (url.indexOf("/auth/v1/") !== -1) {
      return Promise.resolve(json({}));
    }

    var path = url;
    try {
      path = new URL(url, window.location.origin).pathname;
    } catch (e) {}

    if (Object.prototype.hasOwnProperty.call(F, path)) {
      return Promise.resolve(json(F[path]));
    }
    // Fail soft for un-fixtured product endpoints: an empty 200 renders an
    // empty section, whereas a network error would surface an error banner
    // across the whole surface.
    if (path.indexOf("/api/") === 0) {
      return Promise.resolve(json({}));
    }
    return realFetch(input, init);
  };

  // Org selection and dismissed first-run overlays are read from web storage,
  // not the API, so seed them here.
  try {
    localStorage.setItem("gravitre:selectedOrg", JSON.stringify({ id: F.__orgId, name: "Northwind Logistics" }));
    localStorage.setItem("gravitre-welcome-dismissed", "true");
    localStorage.removeItem("gravitre-nav-expanded");
    sessionStorage.removeItem("gravitre-trial-banner-dismissed");
  } catch (e) {}
})();
`.trim()

  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: bootstrap }} />
      {children}
    </>
  )
}
