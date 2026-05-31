/** @type {import('next').NextConfig} */
const nextConfig = {
  // Type errors now fail the build (tsc is clean). Keep it that way via CI + typecheck.
  images: {
    unoptimized: true,
  },
  // Proxy /api/* requests to the FastAPI backend
  async rewrites() {
    const backendUrl = process.env.FASTAPI_BASE_URL || "http://localhost:8000"
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
    ]
  },
}

export default nextConfig
