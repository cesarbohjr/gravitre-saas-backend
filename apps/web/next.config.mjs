import path from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const fastApiBase = (process.env.FASTAPI_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "")

/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    return [
      {
        source: "/fastapi/:path*",
        destination: `${fastApiBase}/:path*`,
      },
    ]
  },
}

export default nextConfig
