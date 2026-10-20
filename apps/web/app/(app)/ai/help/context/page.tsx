"use client"

import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { ArrowLeft, BookOpen } from "lucide-react"
import { APP_ROUTES } from "@/lib/app-routes"
import { CUSTOMER_DATA_SETTINGS_HREF } from "@/lib/context-sources"

const LINK = "text-foreground underline-offset-2 hover:underline"

/**
 * In-app explainer for the context layer: what Gravitre reads to answer, how
 * freshness and disconnected tools are handled, what is never read, org memory,
 * and customer sentiment. Linked from "Why this answer?", /ai/help/control,
 * Settings › Customer data, the Intelligence overview and the public docs.
 * Honest product claims only; it changes no setting.
 */
export default function HowGravitreUsesYourContextPage() {
  return (
    <AppShell title="How Gravitre uses your context">
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
              <BookOpen className="h-5 w-5 text-foreground" aria-hidden />
            </div>
            <div className="space-y-1">
              <h1 className="text-xl font-semibold tracking-tight text-foreground md:text-2xl">
                How Gravitre uses your context
              </h1>
              <p className="text-sm text-muted-foreground">
                What Gravitre reads to answer you, what it leaves out, and how to switch each part off.
              </p>
            </div>
          </div>
        </div>

        <ol className="space-y-6">
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">What it reads</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              For each question Gravitre picks the most relevant pieces from three places: your{" "}
              <Link href={APP_ROUTES.connectors} className={LINK}>
                connected tools
              </Link>{" "}
              (only the ones you connected, with the access you granted), your knowledge (documents you added or
              synced), and memory (what it remembers from this conversation, your agents, and your organization).
              It searches the web only when a question needs it.
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Under an answer, <span className="text-foreground">Why this answer?</span> lists the sources that
              reply used, how recently each was updated when that is known, and anything it left out and why.
            </p>
          </li>
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">Old and disconnected sources</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              When a document has been replaced or has passed its end date, Gravitre leaves it out and prefers the
              newer one. Knowledge that came from a tool you have not connected, and documents that were deleted,
              are left out too. Some of these checks are still rolling out, so Why this answer? only lists the
              checks that actually ran for that reply.
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              &ldquo;Updated&rdquo; next to a source is when that source last changed. It is different from the
              &ldquo;Refreshed&rdquo; time at the top of a page, which is when the page last loaded its data.
            </p>
          </li>
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">What it never reads</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Internal chat between colleagues is never used to judge customers, and email written by your own
              colleagues is left out of customer sentiment. Gravitre only reads tools you connected, and only
              within the access each connection allows.
            </p>
          </li>
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">Organization memory</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              When the same fact keeps showing up across agent runs and teams, Gravitre proposes it as a shared
              memory. In{" "}
              <Link href={APP_ROUTES.intelligenceMemory} className={LINK}>
                Knowledge › Memory
              </Link>{" "}
              each memory shows where it came from: the kind of source, the agents and teams that saw it, and the
              connected tool it was learned from when that was recorded. Admins approve or reject proposed
              memories, and can roll back one that was shared automatically.
            </p>
          </li>
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">Customer sentiment</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              With customer context switched on, email from your customers in the systems you choose is judged
              for tone, urgency, churn-risk language, interest in buying more, and support problems. Every
              reading quotes the customer&apos;s own words as evidence, and a trend needs several messages before
              Gravitre calls it one. Results appear in{" "}
              <Link href={APP_ROUTES.intelligenceAccounts} className={LINK}>
                Intelligence › Accounts
              </Link>
              . This is off by default and nothing is read until an admin turns it on.
            </p>
          </li>
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">From a finding to useful work</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              Accounts and Forecasts show evidence-backed next steps. Review a relevant Play, such as Customer
              Rescue, or prepare a review assignment with the finding and evidence already in its brief. Review
              prerequisites and approve the work before starting. Accepting a proposal only adds planned work;
              customer-facing changes still require their normal approval.
            </p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              A sentiment reading describes customer language. A forecast estimates a future result. When they
              disagree, compare both sources. Completion and verified business results feed outcome learning;
              a chat reply or an accepted suggestion does not prove that a model learned or a customer was retained.
              Analyzing text pasted into chat does not create a stored customer reading by itself.
            </p>
          </li>
          <li className="space-y-1.5">
            <h2 className="text-sm font-semibold text-foreground">Turning things on and off</h2>
            <ul className="list-disc space-y-1 pl-4 text-sm leading-relaxed text-muted-foreground">
              <li>
                Customer context and how long documents are kept:{" "}
                <Link href={CUSTOMER_DATA_SETTINGS_HREF} className={LINK}>
                  Settings › Customer data
                </Link>{" "}
                (admins).
              </li>
              <li>
                Which tools Gravitre can read:{" "}
                <Link href={APP_ROUTES.connectors} className={LINK}>
                  Connectors
                </Link>
                . Disconnecting a tool removes what Gravitre kept from it.
              </li>
              <li>
                A single memory:{" "}
                <Link href={APP_ROUTES.intelligenceMemory} className={LINK}>
                  Knowledge › Memory
                </Link>
                , then reject or roll it back.
              </li>
            </ul>
          </li>
        </ol>

        <div className="flex flex-wrap gap-2 border-t border-border pt-6">
          <Button asChild variant="outline" size="sm">
            <Link href={CUSTOMER_DATA_SETTINGS_HREF}>Open customer data settings</Link>
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link href="/ai/help/control">How Gravitre keeps you in control</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/docs/concepts/context">Read the docs version</Link>
          </Button>
        </div>
      </div>
    </AppShell>
  )
}
