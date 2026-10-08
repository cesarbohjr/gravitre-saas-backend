"use client"

import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { ArrowLeft, ShieldCheck } from "lucide-react"

/**
 * Item 1 — short in-app trust explainer reachable from chat.
 * Honest product claims only; does not change write gates.
 */
export default function HowGravitreKeepsYouInControlPage() {
  return (
    <AppShell title="How Gravitre keeps you in control">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-8 px-4 py-8 md:px-6">
        <div className="space-y-3">
          <Link
            href="/ai"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to chat
          </Link>
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-md border border-border bg-secondary/40 p-2">
              <ShieldCheck className="h-5 w-5 text-foreground" aria-hidden />
            </div>
            <div className="space-y-1">
              <h1 className="text-xl font-semibold tracking-tight text-foreground md:text-2xl">
                How Gravitre keeps you in control
              </h1>
              <p className="text-sm text-muted-foreground">
                A short, honest summary of how writes, results, and guesses work — not a wall of
                docs.
              </p>
            </div>
          </div>
        </div>

        <ol className="space-y-6">
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">Every write asks first</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Connector writes and other mutating actions go through the same approval / confirm
              gate as the rest of the platform. Suggestion cards and chat never skip that path.
            </p>
          </li>
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">Every result links back to the real thing</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Successful tool runs surface sources, connector status, and the org{" "}
              <Link href="/audit" className="text-foreground underline-offset-2 hover:underline">
                audit trail
              </Link>{" "}
              so you can verify what actually happened — not just trust a chat summary.
            </p>
          </li>
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">Every guess is labeled</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              When Gravitre fills a missing field or makes an assumption, it shows up as an
              assumption note or inferred field — not as silent certainty.
            </p>
          </li>
        </ol>

        <div className="flex flex-wrap gap-2 border-t border-border pt-6">
          <Button asChild variant="outline" size="sm">
            <Link href="/audit">Open audit trail</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/approvals">Open approvals</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/docs/concepts/control">Read the docs version</Link>
          </Button>
        </div>
      </div>
    </AppShell>
  )
}
