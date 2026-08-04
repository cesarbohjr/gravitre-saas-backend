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
  if (
    process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E !== "1" &&
    process.env.PLAYWRIGHT_E2E !== "1"
  ) {
    notFound()
  }

  const bootstrap = `
(function () {
  var F = ${JSON.stringify(SHOT_FIXTURES)};
  var realFetch = window.fetch.bind(window);

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
