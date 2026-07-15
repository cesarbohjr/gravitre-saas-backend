import type { ReactNode } from "react"

/** Canonical production origin used for metadata, canonical URLs, and JSON-LD. */
export const SITE_URL = "https://gravitre.app"

export type BlogAuthor = {
  name: string
  role: string
  /** Optional headshot. When omitted, the UI renders a brand monogram avatar. */
  image?: string
  /** Authoritative profile URLs for the Person schema `sameAs` (helps E-E-A-T / GEO). */
  sameAs?: string[]
}

export type BlogFAQ = {
  question: string
  answer: string
}

export type BlogPost = {
  slug: string
  title: string
  /** <=160 chars, written as a direct answer for AEO/meta description. */
  description: string
  excerpt: string
  category: string
  author: BlogAuthor
  /** ISO 8601 for schema + <time>. Use createBlogDates() with the go-live day when publishing. */
  datePublished: string
  /** ISO 8601; bump when article content changes after publish. */
  dateModified: string
  /** Human-readable display date (derived from datePublished). */
  displayDate: string
  readTime: string
  heroImage: string
  /** Tailwind gradient classes when no hero image asset exists. */
  heroGradient?: string
  heroAlt: string
  keywords: string[]
  /** Short, extractable summary points surfaced to answer engines and readers. */
  takeaways: string[]
  faqs: BlogFAQ[]
  /** Rendered article body. */
  Content: () => ReactNode
}
