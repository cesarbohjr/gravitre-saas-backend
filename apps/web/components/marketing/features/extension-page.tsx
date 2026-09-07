"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  CheckCircle2,
  ListChecks,
  MessageSquare,
  Shield,
  Workflow,
} from "lucide-react"
import {
  extensionInstallCtaLabel,
  extensionInstallHref,
} from "@/lib/extension-install"
import { ProductScreenshot } from "@/components/marketing/product-screenshot"
import { BrowserFrame } from "@/components/marketing/browser-frame"
import {
  BraveVendorIcon,
  ChromeVendorIcon,
  EdgeVendorIcon,
} from "@/components/marketing/browser-vendor-icons"
import { Button } from "@/components/marketing/nodus/button"
import { MarketingPageEndCta, MarketingPageHero, MarketingRails } from "@/components/marketing/nodus/page-shell"
import { DivideX } from "@/components/marketing/nodus/divide"

const activationSteps = [
  {
    n: "1",
    title: "Install",
    body: "Add Gravitre from the Chrome Web Store (works in Chrome, Edge, and Brave).",
  },
  {
    n: "2",
    title: "Connect",
    body: "Authorize from the popup — same org session as gravitre.app. No second identity system.",
  },
  {
    n: "3",
    title: "Enrich",
    body: "Open a LinkedIn profile (or Gmail / Outlook / company page). Overlay runs catalog reads from page context.",
  },
  {
    n: "4",
    title: "Approve a write",
    body: "Confirm once. Creates go through catalog write authority — not DOM clicking in HubSpot or Apollo.",
  },
  {
    n: "5",
    title: "See Outcomes",
    body: "The run lands in Outcomes / Runs with source browser_extension — same visibility as chat.",
  },
] as const

/** Proven with enrich + approved write + Outcomes (v1 / v2 gate). */
const surfacesProven = [
  "LinkedIn profiles",
  "Gmail",
  "Outlook on the web",
  "Company websites (when you invoke Enrich)",
  "Careers / about pages (path-matched)",
  "Salesforce Lightning / Force hosts",
  "Slack web (app.slack.com)",
] as const

export function ExtensionPage() {
  const installHref = extensionInstallHref()
  const installLabel = extensionInstallCtaLabel()
  const storeListing = installHref.startsWith("http")

  return (
    <div className="bg-white">
      <MarketingPageHero
        badge="Chrome · Edge · Brave · overlay and approve"
        title={
          <>
            Enrich the page. <span className="text-brand">Approve the write.</span>
          </>
        }
        description="Gravitre lives where you already work: LinkedIn, Gmail, Outlook, company sites. Real actions, not guesses. Your approval before every write. Full audit in Outcomes. Not another CRM bot — just Gravitre, closer."
      >
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button
            as="a"
            href={installHref}
            {...(storeListing
              ? { target: "_blank", rel: "noopener noreferrer" }
              : {})}
          >
            {installLabel}
          </Button>
          <Button as={Link} href="/docs/guides/how-to/browser-extension" variant="secondary">
            Setup guide
          </Button>
        </div>
        <ul
          aria-label="Supported browsers"
          className="mt-10 flex items-end justify-center gap-8 sm:gap-10"
        >
          {(
            [
              { label: "Chrome", Icon: ChromeVendorIcon },
              { label: "Edge", Icon: EdgeVendorIcon },
              { label: "Brave", Icon: BraveVendorIcon },
            ] as const
          ).map(({ label, Icon }) => (
            <li key={label} className="flex flex-col items-center gap-2.5">
              <span className="border-divide flex h-14 w-14 items-center justify-center rounded-2xl border bg-gray-50">
                <Icon className="h-7 w-7" />
              </span>
              <span className="text-xs font-medium text-gray-600">{label}</span>
            </li>
          ))}
        </ul>
      </MarketingPageHero>

      <DivideX />

      <MarketingRails>
          <h2 className="text-center text-2xl font-medium text-charcoal-700 sm:text-3xl">
            Activation in five steps
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-gray-600">
            The milestone that matters: install → connect → enrich → approve →
            Outcomes. Minutes, not a project plan.
          </p>
          <ol className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {activationSteps.map((step, i) => (
              <motion.li
                key={step.n}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="rounded-lg border border-divide bg-gray-50 p-5"
              >
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-sm font-bold text-primary">
                  {step.n}
                </div>
                <h3 className="font-semibold text-foreground">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
              </motion.li>
            ))}
          </ol>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
          <h2 className="text-center text-2xl font-medium text-charcoal-700 sm:text-3xl">
            Steps 3 and 4, on the page
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-gray-600">
            The overlay opens beside whatever you are already looking at. You
            never leave the tab to enrich, and you never leave it to approve.
          </p>
          <div className="mt-12 grid gap-10 lg:grid-cols-2">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <h3 className="font-semibold text-foreground">
                Step 3 — enrich from page context
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                Catalog reads run against the tab you are on. Nothing is read
                until you open the overlay.
              </p>
              <BrowserFrame
                className="mt-5"
                url="linkedin.com/in/…"
                tabTitle="LinkedIn"
                panel={{
                  src: "/product/extension-overlay-enrich.png",
                  alt: "Gravitre overlay panel open on a LinkedIn profile, showing enriched company and contact fields pulled from catalog reads.",
                  width: 760,
                  height: 1802,
                }}
              />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.05 }}
            >
              <h3 className="font-semibold text-foreground">
                Step 4 — confirm the write
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                The overlay names the exact catalog action before anything is
                committed. One confirmation, in the same panel.
              </p>
              <BrowserFrame
                className="mt-5"
                url="linkedin.com/in/…"
                tabTitle="LinkedIn"
                // The confirm block is at the end of this panel — anchor to
                // the bottom so the actual approval is what you see.
                panelAlign="bottom"
                panel={{
                  src: "/product/extension-approval.png",
                  alt: "Gravitre overlay panel showing a staged HubSpot contact create awaiting confirmation, with the catalog action and target fields listed.",
                  width: 760,
                  height: 2358,
                }}
              />
            </motion.div>
          </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
          <p className="text-center text-xs font-semibold uppercase tracking-wide text-gray-500">
            Supporting proof
          </p>
          <h2 className="mt-2 text-center text-xl font-medium text-charcoal-700">
            No separate queue, no separate audit trail
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-sm text-gray-600">
            The overlay does not get its own approval queue or audit trail. A
            staged write waits in the same Approvals queue as chat, and the run
            lands in the same Activity feed — tagged with its source.
          </p>
          {/* Stacked, not side-by-side: these are dense product surfaces, and at
              half of max-w-5xl the in-app text is too small to read, which turns
              the proof into decoration. */}
          <div className="mt-12 flex flex-col gap-14">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <h3 className="text-sm font-semibold text-foreground">
                Step 4, in the app — the shared Approvals queue
              </h3>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                The same confirmation you just saw in the overlay also appears
                here, with the exact catalog action, its blast radius, and who
                asked for it.
              </p>
              <ProductScreenshot
                className="mt-5"
                src="/product/app-approvals.png"
                alt="Approvals queue showing three pending requests, with a HubSpot contact create selected and its recommendation, SLA, and impact detail open."
              />
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <h3 className="text-sm font-semibold text-foreground">
                Step 5, in the app — see it in Outcomes
              </h3>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted-foreground">
                Extension runs appear with source{" "}
                <code className="rounded bg-muted px-1 py-0.5 text-xs text-foreground">
                  browser_extension
                </code>{" "}
                and the same lifecycle chain as chat — planned, approved,
                executed, verified.
              </p>
              <ProductScreenshot
                className="mt-5"
                src="/product/app-activity.png"
                alt="Activity feed listing runs with lifecycle state and source, including a created HubSpot contact run sourced from the browser extension."
              />
            </motion.div>
          </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails className="grid gap-10 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-medium text-charcoal-700">Supported surfaces</h2>
            <p className="mt-3 text-gray-600">
              Explicit host allowlist — no silent expansion. Page context only;
              creates and list membership use governed catalog actions (Apollo /
              HubSpot where connected). Outside-allowlist attempts are recorded
              as usage signals for prioritization, not as new permissions.
            </p>
            <ul className="mt-6 space-y-3">
              {surfacesProven.map((s) => (
                <li key={s} className="flex items-start gap-2 text-foreground">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-sm text-muted-foreground">
              Salesforce and Slack overlays use page context plus connected
              catalog actions (Apollo / HubSpot today). Native Salesforce lead
              search/create and Slack user lookup activate when those connectors
              are connected — still catalog only, never DOM automation.
            </p>
          </div>
          <div className="space-y-4">
            <div className="rounded-lg border border-divide bg-gray-50 p-5">
              <Shield className="mb-3 h-6 w-6 text-primary" />
              <h3 className="font-semibold text-foreground">Same governance as chat</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Writes stage awaiting confirmation with a server-issued token.
                Org membership is enforced. Outcomes use Module A finalize —
                not a side channel.
              </p>
            </div>
            <div className="rounded-lg border border-divide bg-gray-50 p-5">
              <ListChecks className="mb-3 h-6 w-6 text-primary" />
              <h3 className="font-semibold text-foreground">What it will not do</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                No InMail spam, no clicking Salesforce/HubSpot UI for you, no
                agentic multi-step form control. If a catalog action exists, we
                call it.
              </p>
            </div>
            <div className="rounded-lg border border-divide bg-gray-50 p-5">
              <MessageSquare className="mb-3 h-6 w-6 text-primary" />
              <h3 className="font-semibold text-foreground">Quick chat on the page</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Ask a short, page-contextual question in the overlay — same
                unified-turn path as Gravitre chat. Writes and multi-step work
                hand off to the full app on the same conversation thread (where
                the progress panel lives). Proven thread:{" "}
                <a
                  className="font-medium text-primary underline-offset-2 hover:underline"
                  href="https://gravitre.app/ai?c=cc618049-0d01-481a-95f7-7b87ad045ae9"
                  target="_blank"
                  rel="noreferrer"
                >
                  overlay Q → write handoff
                </a>
                .
              </p>
            </div>
            <div className="rounded-lg border border-divide bg-gray-50 p-5">
              <Workflow className="mb-3 h-6 w-6 text-primary" />
              <h3 className="font-semibold text-foreground">Workflows from the overlay</h3>
              <p className="mt-2 text-sm text-muted-foreground">
                Trigger existing typed workflows with the same plan-bar approve
                pattern as chat — named step labels stay visible while it runs,
                then open the Outcomes chain. Proven runs:{" "}
                <a
                  className="font-medium text-primary underline-offset-2 hover:underline"
                  href="https://gravitre.app/outcomes/139fd6cc-7d53-4dfd-ac1b-c59e902109ea"
                  target="_blank"
                  rel="noreferrer"
                >
                  NVD + CISA KEV
                </a>
                ,{" "}
                <a
                  className="font-medium text-primary underline-offset-2 hover:underline"
                  href="https://gravitre.app/outcomes/54914197-9516-48c3-90be-703980deb6ec"
                  target="_blank"
                  rel="noreferrer"
                >
                  HubSpot pipelines + deals
                </a>
                ,{" "}
                <a
                  className="font-medium text-primary underline-offset-2 hover:underline"
                  href="https://gravitre.app/outcomes/6d314587-bafb-4b11-a78b-da6c4d5245d6"
                  target="_blank"
                  rel="noreferrer"
                >
                  Apollo orgs + HubSpot pipelines
                </a>
                .
              </p>
            </div>
          </div>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
