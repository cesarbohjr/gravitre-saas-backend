import type { MetadataRoute } from "next"

/** Public marketing routes only. Do not expose signed-in workspaces or API URLs. */
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://gravitre.app"
  const paths = [
    "/", "/about", "/pricing", "/features", "/features/technology",
    "/features/extension", "/features/marketplace", "/security",
    "/blog", "/guides", "/contact", "/careers", "/download",
    "/changelog", "/roadmap", "/privacy", "/terms",
  ]
  return paths.map((path) => ({
    url: new URL(path, base).toString(),
    changeFrequency: path === "/blog" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : ["/pricing", "/features", "/about"].includes(path) ? 0.8 : 0.5,
  }))
}
