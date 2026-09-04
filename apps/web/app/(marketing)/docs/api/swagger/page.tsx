import type { Metadata } from "next"
import Link from "next/link"
import { ArrowLeft, KeyRound, Globe, Gauge, FileJson } from "lucide-react"

import { SwaggerExplorer } from "@/components/docs/swagger-explorer"

export const metadata: Metadata = {
  title: "API reference · Gravitre Docs",
  description:
    "Interactive explorer for the public Gravitre REST API — authentication, endpoints, and live try-it-out.",
}

const META_CARDS = [
  { icon: Globe, label: "Base URL", value: "https://gravitre.app/api" },
  { icon: KeyRound, label: "Auth", value: "Bearer API key" },
  { icon: Gauge, label: "Rate limit", value: "600 req / min" },
]

export default function ApiSwaggerPage() {
  const specUrl = "/docs/api/openapi.json"

  return (
    <div className="min-h-screen bg-card">
      <section className="border-b border-border bg-gradient-to-b from-muted/50 to-white px-6 py-10">
        <div className="mx-auto max-w-6xl">
          <Link
            href="/docs/api/quickstart"
            className="mb-6 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-primary"
          >
            <ArrowLeft className="h-4 w-4" />
            API quickstart
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">API reference</h1>
          <p className="mt-3 max-w-3xl text-muted-foreground">
            Interactive explorer for the public Gravitre REST API. Authorize with your API key and
            run requests directly from the browser. Internal admin routes are omitted from the
            published spec.
          </p>

          <div className="mt-6 grid gap-3 sm:grid-cols-3">
            {META_CARDS.map((card) => {
              const Icon = card.icon
              return (
                <div
                  key={card.label}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs text-muted-foreground">{card.label}</p>
                    <p className="truncate font-mono text-sm text-foreground">{card.value}</p>
                  </div>
                </div>
              )
            })}
          </div>

          <p className="mt-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
            <FileJson className="h-4 w-4" />
            Raw spec:{" "}
            <a className="font-medium text-primary hover:underline" href={specUrl}>
              {specUrl}
            </a>
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-2 py-6 sm:px-6">
        <SwaggerExplorer specUrl={specUrl} />
      </section>
    </div>
  )
}
