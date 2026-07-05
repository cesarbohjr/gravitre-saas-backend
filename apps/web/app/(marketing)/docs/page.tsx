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
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="relative mx-auto max-w-4xl text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-zinc-900 sm:text-5xl">
            Documentation
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-zinc-600">
            {MARKETING_COPY.docs.description}
          </p>
          <div className="mx-auto mt-8 max-w-xl">
            <DocsSearch index={searchIndex} placeholder="Search guides, concepts, and API reference…" />
          </div>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-sm">
            <Link
              href="/docs/getting-started/quickstart"
              className="rounded-full bg-zinc-900 px-5 py-2.5 font-medium text-white transition-colors hover:bg-zinc-800"
            >
              Start here
            </Link>
            <Link
              href="/docs/guides/how-to/org-learning"
              className="rounded-full border border-zinc-200 px-5 py-2.5 text-zinc-700 transition-colors hover:border-emerald-300 hover:text-emerald-700"
            >
              GIBE (Learning)
            </Link>
            <Link
              href="/docs/api/swagger"
              className="rounded-full border border-zinc-200 px-5 py-2.5 text-zinc-700 transition-colors hover:border-emerald-300 hover:text-emerald-700"
            >
              API explorer
            </Link>
          </div>
        </div>
      </section>

      <section className="px-6 pb-16">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-6 text-sm font-medium uppercase tracking-wide text-zinc-500">
            Popular guides
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {quickLinks.map((link) => {
              const Icon = link.icon
              return (
                <Link
                  key={link.title}
                  href={link.href}
                  className="group block rounded-xl border border-zinc-200 bg-white p-5 transition-all hover:border-emerald-300 hover:shadow-md"
                >
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 transition-colors group-hover:bg-emerald-100">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="font-medium text-zinc-900 transition-colors group-hover:text-emerald-700">
                    {link.title}
                  </h3>
                  <p className="mt-1 text-sm text-zinc-500">{link.description}</p>
                </Link>
              )
            })}
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-200 px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <div className="mb-8 flex items-center justify-between">
            <h2 className="text-2xl font-semibold text-zinc-900">Featured how-to guides</h2>
            <Link
              href="/docs/guides/how-to/ai-operator"
              className="flex items-center gap-1 text-sm text-emerald-600 hover:text-emerald-500"
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
                className="group flex items-center justify-between rounded-lg border border-zinc-200 bg-white p-4 transition-all hover:border-emerald-300 hover:shadow-sm"
              >
                <div>
                  <span className="text-xs text-emerald-600">{guide.frontmatter.category}</span>
                  <h3 className="mt-0.5 text-sm font-medium text-zinc-900 group-hover:text-emerald-700">
                    {guide.frontmatter.title}
                  </h3>
                </div>
                {guide.frontmatter.readTime ? (
                  <span className="text-xs text-zinc-400">{guide.frontmatter.readTime}</span>
                ) : null}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-200 bg-zinc-50 px-6 py-16">
        <div className="mx-auto max-w-5xl">
          <div className="mb-8 max-w-2xl">
            <h2 className="text-2xl font-semibold text-zinc-900">Browse by topic</h2>
            <p className="mt-2 text-zinc-600">
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
                  className="group flex flex-col rounded-xl border border-zinc-200 bg-white p-5 transition-all hover:border-emerald-300 hover:shadow-md"
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 transition-colors group-hover:bg-emerald-100">
                    <Icon className="h-5 w-5" />
                  </div>
                  <h3 className="font-medium text-zinc-900 transition-colors group-hover:text-emerald-700">
                    {section.title}
                  </h3>
                  <p className="mt-1 text-sm leading-relaxed text-zinc-500">
                    {categoryDescription(section.title)}
                  </p>
                  <div className="mt-auto flex items-center gap-1 pt-4 text-sm font-medium text-emerald-600">
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
      </section>

      <section className="border-t border-zinc-200 px-6 py-16">
        <div className="mx-auto max-w-4xl">
          <div className="rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm">
            <div className="mb-4 flex items-center gap-3">
              <Terminal className="h-6 w-6 text-emerald-600" />
              <h2 className="text-xl font-semibold text-zinc-900">API reference</h2>
            </div>
            <p className="mb-6 text-zinc-600">
              REST API at <code className="rounded bg-zinc-100 px-1">https://gravitre.app/api</code>.
              OpenAPI spec and Swagger UI for integrators.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/docs/api/swagger"
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-2 text-sm text-zinc-900 transition-colors hover:bg-zinc-100"
              >
                Swagger UI
              </Link>
              <Link
                href="/docs/api/openapi.json"
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 px-4 py-2 text-sm text-zinc-600 transition-colors hover:border-zinc-300 hover:text-zinc-900"
              >
                openapi.json
              </Link>
              <Link
                href="/docs/api/quickstart"
                className="inline-flex items-center gap-2 rounded-lg border border-zinc-200 px-4 py-2 text-sm text-zinc-600 transition-colors hover:border-zinc-300 hover:text-zinc-900"
              >
                API quickstart
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-zinc-200 bg-zinc-50 px-6 py-16">
        <div className="mx-auto max-w-4xl text-center">
          <h2 className="mb-4 text-2xl font-semibold text-zinc-900">Need help?</h2>
          <p className="mb-8 text-zinc-600">
            See the <Link href="/docs/faq" className="text-emerald-700 hover:underline">FAQ</Link> or
            contact our team.
          </p>
          <Link
            href="/contact"
            className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-medium text-white transition-all hover:bg-zinc-800"
          >
            Contact support
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </section>
    </div>
  )
}
