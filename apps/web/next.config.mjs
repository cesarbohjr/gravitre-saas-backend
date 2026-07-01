/** @type {import('next').NextConfig} */
const nextConfig = {
  // Type errors now fail the build (tsc is clean). Keep it that way via CI + typecheck.
  images: {
    unoptimized: true,
  },
  // Proxy /api/* requests to the FastAPI backend
  async rewrites() {
    const backendUrl = (process.env.FASTAPI_BASE_URL || "http://localhost:8000")
      .trim()
      .replace(/[\r\n]+/g, "")
      .replace(/\/+$/, "")
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ]
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
    ]
  },
}

export default nextConfig
