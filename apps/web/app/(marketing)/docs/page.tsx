import Link from "next/link"
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  Brain,
  Code,
  Database,
  MessageSquare,
  Package,
  Terminal,
  Workflow,
  Zap,
} from "lucide-react"

import type { Metadata } from "next"

import { getDocsNavSections, getPublishedPublicDocs, getDocsSearchIndex } from "@/lib/docs/load-docs"
import { DocsSearch } from "@/components/docs/docs-search"
import { categoryIcon, categoryDescription, categoryLanding } from "@/components/docs/category-meta"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { MarketingPageHero, MarketingRails, MarketingPageEndCta } from "@/components/marketing/nodus/page-shell"

const DOC_ICON_MAP = {
  Zap,
  Brain,
  Bot,
  Database,
  Workflow,
  Activity,
  BarChart3,
  Code,
  MessageSquare,
  Terminal,
  Package,
} as const

const quickLinks = MARKETING_COPY.docs.quickLinks.map((link) => ({
  ...link,
  icon: DOC_ICON_MAP[link.iconKey as keyof typeof DOC_ICON_MAP] ?? Zap,
}))

const title = `${MARKETING_COPY.docs.title} | Gravitre`
const description = MARKETING_COPY.docs.description

export const metadata: Metadata = {
  title,
  description,
  openGraph: {
    title,
    description,
    images: [{ url: "/og-docs.png", width: 1200, height: 630, alt: "Gravitre Docs" }],
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
    images: ["/og-docs.png"],
  },
}

const FEATURED_GUIDE_SLUGS = [
  "guides/how-to/org-learning",
  "guides/how-to/assistant",
  "guides/how-to/connectors",
  "guides/how-to/workflows",
  "guides/how-to/failure-alerts",
  "guides/how-to/runs",
  "guides/how-to/metrics",
  "guides/how-to/training",
]

export default function DocsPage() {
  const sections = getDocsNavSections()
  const allDocs = getPublishedPublicDocs()
  const searchIndex = getDocsSearchIndex()
  const docsBySlug = new Map(allDocs.map((d) => [d.slug, d]))

  const featuredGuides = FEATURED_GUIDE_SLUGS.map((slug) => docsBySlug.get(slug)).filter(
    (doc): doc is NonNullable<typeof doc> => Boolean(doc),
  )

  return (
    <div className="bg-white">
      <MarketingPageHero
        badge="Documentation"
        title="Documentation"
        description={MARKETING_COPY.docs.description}
      >
        <div className="mx-auto mt-8 max-w-xl">
          <DocsSearch index={searchIndex} placeholder="Search guides, concepts, and API reference…" />
        </div>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-sm">
          <Link
            href="/docs/getting-started/quickstart"
            className="rounded-full bg-foreground px-5 py-2.5 font-medium text-white transition-colors hover:bg-foreground/90"
          >
            Start here
          </Link>
          <Link
            href="/docs/guides/how-to/org-learning"
            className="rounded-full border border-border px-5 py-2.5 text-foreground transition-colors hover:border-primary/30 hover:text-primary"
          >
            GIBE (Learning)
          </Link>
          <Link
            href="/docs/api/swagger"
            className="rounded-full border border-border px-5 py-2.5 text-foreground transition-colors hover:border-primary/30 hover:text-primary"
          >
            API explorer
          </Link>
        </div>
      </MarketingPageHero>

      <MarketingRails>
        <div className="mb-16">
          <h2 className="mb-6 text-sm font-medium uppercase tracking-wide text-muted-foreground">
            Popular guides
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {quickLinks.map((link) => {
              const Icon = link.icon
              return (
                <Link
                  key={link.title}
                  href={link.href}
                  className="group block rounded-xl border border-border bg-gray-50 p-5 transition-all hover:border-primary/30 hover:bg-white"
                >
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary/15">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="font-medium text-foreground transition-colors group-hover:text-primary">
                    {link.title}
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">{link.description}</p>
                </Link>
              )
            })}
          </div>
        </div>

        <div className="mb-16 border-t border-border pt-12">
          <div className="mb-8 flex items-center justify-between">
            <h2 className="text-2xl font-semibold text-foreground">Featured how-to guides</h2>
            <Link
              href="/docs/guides/how-to/ai-operator"
              className="flex items-center gap-1 text-sm text-primary hover:text-primary"
            >
              Full guide index
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {featuredGuides.map((guide) => (
              <Link
                key={guide.slug}
                href={`/docs/${guide.slug}`}
                className="group flex items-center justify-between rounded-lg border border-border bg-card p-4 transition-all hover:border-primary/30 hover:shadow-sm"
              >
                <div>
                  <span className="text-xs text-primary">{guide.frontmatter.category}</span>
                  <h3 className="mt-0.5 text-sm font-medium text-foreground group-hover:text-primary">
                    {guide.frontmatter.title}
                  </h3>
                </div>
                {guide.frontmatter.readTime ? (
                  <span className="text-xs text-muted-foreground">{guide.frontmatter.readTime}</span>
                ) : null}
              </Link>
            ))}
          </div>
        </div>

        <div className="border-t border-border pt-12">
          <div className="mb-8 max-w-2xl">
            <h2 className="text-2xl font-semibold text-foreground">Browse by topic</h2>
            <p className="mt-2 text-muted-foreground">
              Jump into a section to see every guide and reference page it contains.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sections.map((section) => {
              const Icon = categoryIcon(section.title)
              const href = categoryLanding(section.title, section.items[0]?.href ?? "/docs")
              const count = section.items.length
              return (
                <Link
                  key={section.title}
                  href={href}
                  className="group flex flex-col rounded-xl border border-border bg-gray-50 p-5 transition-all hover:border-primary/30 hover:bg-white"
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary/15">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="font-medium text-foreground transition-colors group-hover:text-primary">
                    {section.title}
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
                    {categoryDescription(section.title)}
                  </p>
                  <div className="mt-auto flex items-center gap-1 pt-4 text-sm font-medium text-primary">
                    <span>
                      {count} {count === 1 ? "article" : "articles"}
                    </span>
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
