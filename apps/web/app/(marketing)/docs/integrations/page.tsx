import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft, Mail, Plug } from "lucide-react"

import { getPublishedPublicDocs } from "@/lib/docs/load-docs"
import { PlanBadge } from "@/components/docs/plan-badge"

export const metadata: Metadata = {
  title: "Integrations · Gravitre Docs",
  description:
    "Connect Gravitre to the tools your team already uses — CRMs, ticketing, accounting, and more.",
}

/** Map of doc slug (under integrations/) -> self-hosted brand logo. */
const LOGO_BY_SLUG: Record<string, string> = {
  "integrations/github": "/logos/integrations/github.svg",
  "integrations/google-workspace": "/logos/integrations/google-workspace.svg",
  "integrations/hubspot": "/logos/integrations/hubspot.svg",
  "integrations/jira": "/logos/integrations/jira.svg",
  "integrations/odoo": "/logos/integrations/odoo.svg",
  "integrations/pagerduty": "/logos/integrations/pagerduty.svg",
  "integrations/quickbooks": "/logos/integrations/quickbooks.svg",
  "integrations/salesforce": "/logos/integrations/salesforce.svg",
  "integrations/zendesk": "/logos/integrations/zendesk.svg",
}

export default function IntegrationsIndexPage() {
  const integrations = getPublishedPublicDocs()
    .filter((doc) => doc.slug.startsWith("integrations/"))
    .sort((a, b) => a.frontmatter.title.localeCompare(b.frontmatter.title))

  return (
    <div className="min-h-screen bg-white">
      <section className="border-b border-zinc-200 bg-gradient-to-b from-zinc-50 to-white px-6 py-12">
        <div className="mx-auto max-w-5xl">
          <Link
            href="/docs"
            className="mb-6 inline-flex items-center gap-1.5 text-sm text-zinc-500 transition-colors hover:text-emerald-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Docs
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
              <Plug className="h-5 w-5" />
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">Integrations</h1>
          </div>
          <p className="mt-4 max-w-2xl text-lg text-zinc-600">
            Connect Gravitre to the tools your team already uses. Each integration uses OAuth or API
            keys, syncs securely, and exposes actions to workflows and agents.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-12">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {integrations.map((doc) => {
            const logo = LOGO_BY_SLUG[doc.slug]
            return (
              <Link
                key={doc.slug}
                href={`/docs/${doc.slug}`}
                className="group flex flex-col rounded-2xl border border-zinc-200 bg-white p-5 transition-all hover:border-emerald-300 hover:shadow-md"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-zinc-100 bg-zinc-50 p-2">
                    {logo ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={logo || "/placeholder.svg"}
                        alt={`${doc.frontmatter.title} logo`}
                        className="h-full w-full object-contain"
                      />
                    ) : (
                      <Mail className="h-5 w-5 text-emerald-600" />
                    )}
                  </div>
                  {doc.frontmatter.tier && <PlanBadge tier={doc.frontmatter.tier} />}
                </div>
                <h2 className="mt-4 font-medium text-zinc-900 transition-colors group-hover:text-emerald-700">
                  {doc.frontmatter.title.replace(/ integration$/i, "")}
                </h2>
                <p className="mt-1 line-clamp-2 text-sm text-zinc-500">
                  {doc.frontmatter.description}
                </p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-emerald-700">
                  Setup guide
                  <span aria-hidden className="transition-transform group-hover:translate-x-0.5">
                    →
                  </span>
                </span>
              </Link>
            )
          })}
        </div>
      </section>
    </div>
  )
}
