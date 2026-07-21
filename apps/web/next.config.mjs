/** @type {import('next').NextConfig} */

const securityHeaders = [
  { key: "X-DNS-Prefetch-Control", value: "on" },
  {
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(self), geolocation=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // Stripe.js + marketing GTM/GA + Plaid Link must be allowed to load/execute.
      "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://js.stripe.com https://*.js.stripe.com https://cdn.plaid.com https://www.googletagmanager.com https://www.google-analytics.com https://*.googletagmanager.com https://*.google-analytics.com",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "font-src 'self' data:",
      // connect-src already allows https:; sandbox/production Plaid APIs covered.
      "connect-src 'self' https: wss:",
      // Stripe Payment Element + Plaid Link frames + GTM noscript iframe.
      "frame-src 'self' https://js.stripe.com https://*.js.stripe.com https://hooks.stripe.com https://m.stripe.network https://cdn.plaid.com https://*.plaid.com https://www.googletagmanager.com",
      "frame-ancestors 'none'",
    ].join("; "),
  },
]

const nextConfig = {
  // Type errors now fail the build (tsc is clean). Keep it that way via CI + typecheck.
  images: {
    unoptimized: true,
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }]
  },
  // Proxy unmatched /api/* to FastAPI. Use `fallback` so App Router route handlers
  // (e.g. /api/agents, /api/agents/[id]) run first with Supabase BFF logic.
  async rewrites() {
    const raw = (process.env.FASTAPI_BASE_URL || "")
      .trim()
      .replace(/[\r\n]+/g, "")
      .replace(/\/+$/, "")
    const backendUrl =
      raw && !raw.includes("api.gravitre.app")
        ? raw
        : "https://gravitre-saas-backend-production.up.railway.app"
    const resolvedBackendUrl = backendUrl || "http://localhost:8000"
    return {
      fallback: [
        {
          source: "/api/:path*",
          destination: `${resolvedBackendUrl}/api/:path*`,
        },
      ],
    }
  },
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "www.gravitre.app" }],
        destination: "https://gravitre.app/:path*",
        permanent: true,
      },
      { source: "/docs/quickstart", destination: "/docs/getting-started/quickstart", permanent: true },
      { source: "/docs/ai-operator", destination: "/docs/guides/how-to/ai-operator", permanent: true },
      { source: "/docs/workflows", destination: "/docs/guides/how-to/workflows", permanent: true },
      { source: "/docs/connectors", destination: "/docs/guides/how-to/connectors", permanent: true },
      { source: "/docs/introduction", destination: "/docs/concepts/introduction", permanent: true },
      { source: "/docs/architecture", destination: "/docs/concepts/platform-overview", permanent: true },
      { source: "/docs/authentication", destination: "/docs/concepts/authentication", permanent: true },
      { source: "/docs/workspaces", destination: "/docs/concepts/environments", permanent: true },
      { source: "/docs/security", destination: "/docs/concepts/security", permanent: true },
      { source: "/docs/api/reference", destination: "/docs/api/swagger", permanent: true },
      { source: "/chat", destination: "/search", permanent: true },
      { source: "/operator", destination: "/ai", permanent: true },
      { source: "/command-center", destination: "/ai", permanent: true },
      { source: "/assistant", destination: "/ai", permanent: true },
      { source: "/agents/swarm", destination: "/multi-agent-run", permanent: true },
      { source: "/tasks", destination: "/runs", permanent: true },
      { source: "/systems", destination: "/connectors", permanent: true },
      { source: "/admin/intelligence", destination: "/intelligence/learning", permanent: true },
      { source: "/admin/intelligence/:path*", destination: "/intelligence/learning/:path*", permanent: true },
      { source: "/intelligence/models", destination: "/models/built-in", permanent: true },
      { source: "/intelligence/models/:name", destination: "/models/built-in/:name", permanent: true },
      // GIBE + Governance now live on the Technology tab.
      { source: "/technology", destination: "/features/technology", permanent: true },
      { source: "/features/intelligence", destination: "/features/technology", permanent: true },
      { source: "/features/governance", destination: "/features/technology", permanent: true },
      { source: "/features/gibe", destination: "/features/technology", permanent: true },
      // Retired split sub-pages now fold back into the single Features page.
      { source: "/features/agents", destination: "/features", permanent: true },
      { source: "/features/workflows", destination: "/features", permanent: true },
      { source: "/features/meson", destination: "/features", permanent: true },
      { source: "/features/gravitre-ai", destination: "/features", permanent: true },
      { source: "/features/how-it-works", destination: "/features", permanent: true },
      { source: "/features/integrations", destination: "/features", permanent: true },
      { source: "/features/insights", destination: "/features", permanent: true },
    ]
  },
}

export default nextConfig
