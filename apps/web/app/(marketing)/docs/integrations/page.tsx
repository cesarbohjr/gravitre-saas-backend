import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft, Mail, Plug } from "lucide-react"

import { getPublishedPublicDocs } from "@/lib/docs/load-docs"
import { PlanBadge } from "@/components/docs/plan-badge"
import { MARKETING_COPY } from "@/lib/marketing-copy"

export const metadata: Metadata = {
  title: "Integrations · Gravitre Docs",
  description: MARKETING_COPY.docs.integrationsIntro,
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
    <div className="min-h-screen bg-card">
      <section className="border-b border-border bg-gradient-to-b from-muted/50 to-white px-6 py-12">
        <div className="mx-auto max-w-5xl">
          <Link
            href="/docs"
            className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-primary"
          >
            <ArrowLeft className="h-4 w-4" />
            Docs
          </Link>
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Plug className="h-5 w-5" />
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-foreground">Integrations</h1>
          </div>
          <p className="mt-4 max-w-2xl text-lg text-muted-foreground">
            {MARKETING_COPY.docs.integrationsIntro}
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
                className="group flex flex-col rounded-2xl border border-border bg-card p-5 transition-all hover:border-primary/30 hover:shadow-md"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-muted/50 p-2">
                    {logo ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={logo || "/placeholder.svg"}
                        alt={`${doc.frontmatter.title} logo`}
                        className="h-full w-full object-contain"
                      />
                    ) : (
                      <Mail className="h-5 w-5 text-primary" />
                    )}
                  </div>
                  {doc.frontmatter.tier && <PlanBadge tier={doc.frontmatter.tier} />}
                </div>
                <h2 className="mt-4 font-medium text-foreground transition-colors group-hover:text-primary">
                  {doc.frontmatter.title.replace(/ integration$/i, "")}
                </h2>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
                  {doc.frontmatter.description}
                </p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
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
