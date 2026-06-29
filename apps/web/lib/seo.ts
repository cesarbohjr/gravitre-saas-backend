import type { Metadata } from "next"

const OG_IMAGE = {
  url: "/og-get-started.png",
  width: 1200,
  height: 630,
  alt: "Gravitre — AI Operations Platform",
}

/**
 * Build consistent metadata for a marketing page.
 *
 * Next.js shallow-merges metadata across segments: when a child segment
 * declares its own `openGraph`/`twitter` object it REPLACES the parent's
 * entirely (it is not deep-merged), so the shared OG image defined on the
 * marketing layout is dropped unless each page re-declares it. This helper
 * keeps the title/description page-specific while always carrying the shared
 * social-card image so links unfurl with an image everywhere.
 */
export function marketingMetadata(opts: {
  title: string
  description: string
  /** Optional shorter description for social cards; falls back to `description`. */
  ogDescription?: string
}): Metadata {
  const { title, description, ogDescription } = opts
  const social = ogDescription ?? description
  return {
    title,
    description,
    openGraph: {
      type: "website",
      siteName: "Gravitre",
      title: `${title} · Gravitre`,
      description: social,
      images: [OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: `${title} · Gravitre`,
      description: social,
      images: [OG_IMAGE.url],
    },
  }
}
