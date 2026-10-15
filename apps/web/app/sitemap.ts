import type { MetadataRoute } from "next"
import { getAllBlogSlugs, getBlogPost } from "./(marketing)/blog/posts"
import { getPublishedPublicDocs } from "@/lib/docs/load-docs"

/** Real post dates only. Static pages have no lastmod until a source of truth exists. */
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://gravitre.app"
  const paths = [
    "/", "/about", "/pricing", "/features", "/features/technology",
    "/features/extension", "/features/marketplace", "/security", "/docs",
    "/blog", "/guides", "/contact", "/careers", "/download",
    "/changelog", "/roadmap", "/privacy", "/terms",
  ]
  const marketing = paths.map((path) => ({
    url: new URL(path, base).toString(),
    changeFrequency: "monthly" as const,
    priority: path === "/" ? 1 : ["/pricing", "/features", "/about"].includes(path) ? 0.8 : 0.5,
  }))
  const articles = getAllBlogSlugs().flatMap((slug) => {
    const post = getBlogPost(slug)
    if (!post) return []
    return [{ url: `${base}/blog/${post.slug}`, lastModified: new Date(post.dateModified), changeFrequency: "monthly" as const, priority: 0.6 }]
  })
  const docs = getPublishedPublicDocs().map((doc) => ({
    url: `${base}/docs/${doc.slug}`, changeFrequency: "monthly" as const, priority: 0.5,
  }))
  return [...marketing, ...articles, ...docs]
}
