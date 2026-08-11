"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  ArrowRight,
  CheckCircle2,
  Chrome,
  Link2,
  ListChecks,
  MessageSquare,
  Shield,
  Sparkles,
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

const activationSteps = [
  {
    n: "1",
    title: "Install",
    body: "Add the Gravitre extension in Chrome (store listing when published, or load-unpacked beta).",
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

  return (
    <div className="bg-white">
      <section className="relative overflow-hidden pt-28 pb-16 sm:pt-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 via-white to-white" />
        <div className="absolute -top-24 right-0 h-72 w-72 rounded-full bg-teal-200/30 blur-3xl" />
        <div className="relative mx-auto max-w-4xl px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2">
              <Chrome className="h-4 w-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-700">
                Chrome · Edge · Brave · overlay and approve
              </span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl text-balance">
              Enrich the page. Approve the write.{" "}
              <span className="bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent">
                Same Outcomes as chat.
              </span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg text-zinc-600">
              Gravitre on LinkedIn, Gmail, Outlook, and company sites — catalog
              actions only, human approval before writes, full audit in Outcomes.
              Not a parallel CRM bot.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                href={installHref}
                className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-6 py-3 text-sm font-semibold text-white hover:bg-zinc-800"
              >
                {installLabel}
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs/guides/how-to/browser-extension"
                className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-800 hover:bg-zinc-50"
              >
                Setup guide
              </Link>
            </div>
            <ul
              aria-label="Supported browsers"
              className="mt-8 flex items-center justify-center gap-5"
            >
              <li className="flex h-12 w-12 items-center justify-center rounded-2xl border border-zinc-200 bg-white shadow-sm shadow-zinc-900/5">
                <ChromeVendorIcon className="h-7 w-7" />
              </li>
              <li className="flex h-12 w-12 items-center justify-center rounded-2xl border border-zinc-200 bg-white shadow-sm shadow-zinc-900/5">
                <EdgeVendorIcon className="h-7 w-7" />
              </li>
              <li className="flex h-12 w-12 items-center justify-center rounded-2xl border border-zinc-200 bg-white shadow-sm shadow-zinc-900/5">
                <BraveVendorIcon className="h-7 w-7" />
              </li>
            </ul>
          </motion.div>
        </div>
      </section>

      <section className="border-t border-zinc-100 py-16">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="text-center text-2xl font-bold text-zinc-900 sm:text-3xl">
            Activation in five steps
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-zinc-600">
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
                className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm"
              >
                <div className="mb-3 flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-sm font-bold text-emerald-700">
                  {step.n}
                </div>
                <h3 className="font-semibold text-zinc-900">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-zinc-600">{step.body}</p>
              </motion.li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-zinc-100 py-16">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="text-center text-2xl font-bold text-zinc-900 sm:text-3xl">
            Steps 3 and 4, on the page
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-zinc-600">
            The overlay opens beside whatever you are already looking at. You
            never leave the tab to enrich, and you never leave it to approve.
          </p>
          <div className="mt-12 grid gap-10 lg:grid-cols-2">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
            >
              <h3 className="font-semibold text-zinc-900">
                Step 3 — enrich from page context
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600">
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
              <h3 className="font-semibold text-zinc-900">
                Step 4 — confirm the write
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600">
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
        </div>
      </section>

      <section className="border-t border-zinc-100 py-16">
        <div className="mx-auto max-w-5xl px-6">
          <p className="text-center text-xs font-semibold uppercase tracking-wide text-zinc-500">
            Supporting proof
          </p>
          <h2 className="mt-2 text-center text-xl font-bold text-zinc-900">
            No separate queue, no separate audit trail
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-sm text-zinc-600">
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
              <h3 className="text-sm font-semibold text-zinc-900">
                Step 4, in the app — the shared Approvals queue
              </h3>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-600">
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
              <h3 className="text-sm font-semibold text-zinc-900">
                Step 5, in the app — see it in Outcomes
              </h3>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-zinc-600">
                Extension runs appear with source{" "}
                <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs text-zinc-800">
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
        </div>
      </section>

      <section className="border-t border-zinc-100 bg-zinc-50/60 py-16">
        <div className="mx-auto grid max-w-5xl gap-10 px-6 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-bold text-zinc-900">Supported surfaces</h2>
            <p className="mt-3 text-zinc-600">
              Explicit host allowlist — no silent expansion. Page context only;
              creates and list membership use governed catalog actions (Apollo /
              HubSpot where connected). Outside-allowlist attempts are recorded
              as usage signals for prioritization, not as new permissions.
            </p>
            <ul className="mt-6 space-y-3">
              {surfacesProven.map((s) => (
                <li key={s} className="flex items-start gap-2 text-zinc-800">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
            <p className="mt-4 text-sm text-zinc-500">
              Salesforce and Slack overlays use page context plus connected
              catalog actions (Apollo / HubSpot today). Native Salesforce lead
              search/create and Slack user lookup activate when those connectors
              are connected — still catalog only, never DOM automation.
            </p>
          </div>
          <div className="space-y-4">
            <div className="rounded-2xl border border-zinc-200 bg-white p-5">
              <Shield className="mb-3 h-6 w-6 text-emerald-600" />
              <h3 className="font-semibold text-zinc-900">Same governance as chat</h3>
              <p className="mt-2 text-sm text-zinc-600">
                Writes stage awaiting confirmation with a server-issued token.
                Org membership is enforced. Outcomes use Module A finalize —
                not a side channel.
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-200 bg-white p-5">
              <ListChecks className="mb-3 h-6 w-6 text-emerald-600" />
              <h3 className="font-semibold text-zinc-900">What it will not do</h3>
              <p className="mt-2 text-sm text-zinc-600">
                No InMail spam, no clicking Salesforce/HubSpot UI for you, no
                agentic multi-step form control. If a catalog action exists, we
                call it.
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-200 bg-white p-5">
              <MessageSquare className="mb-3 h-6 w-6 text-emerald-600" />
              <h3 className="font-semibold text-zinc-900">Quick chat on the page</h3>
              <p className="mt-2 text-sm text-zinc-600">
                Ask a short, page-contextual question in the overlay — same
                unified-turn path as Gravitre chat. Writes and multi-step work
                hand off to the full app on the same conversation thread (where
                the progress panel lives). Proven thread:{" "}
                <a
                  className="font-medium text-emerald-700 underline-offset-2 hover:underline"
                  href="https://gravitre.app/ai?c=cc618049-0d01-481a-95f7-7b87ad045ae9"
                  target="_blank"
                  rel="noreferrer"
                >
                  overlay Q → write handoff
                </a>
                .
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-200 bg-white p-5">
              <Workflow className="mb-3 h-6 w-6 text-emerald-600" />
              <h3 className="font-semibold text-zinc-900">Workflows from the overlay</h3>
              <p className="mt-2 text-sm text-zinc-600">
                Trigger existing typed workflows with the same plan-bar approve
                pattern as chat — named step labels stay visible while it runs,
                then open the Outcomes chain. Proven runs:{" "}
                <a
                  className="font-medium text-emerald-700 underline-offset-2 hover:underline"
                  href="https://gravitre.app/outcomes/139fd6cc-7d53-4dfd-ac1b-c59e902109ea"
                  target="_blank"
                  rel="noreferrer"
                >
                  NVD + CISA KEV
                </a>
                ,{" "}
                <a
                  className="font-medium text-emerald-700 underline-offset-2 hover:underline"
                  href="https://gravitre.app/outcomes/54914197-9516-48c3-90be-703980deb6ec"
                  target="_blank"
                  rel="noreferrer"
                >
                  HubSpot pipelines + deals
                </a>
                ,{" "}
                <a
                  className="font-medium text-emerald-700 underline-offset-2 hover:underline"
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
        </div>
      </section>

      <section className="border-t border-zinc-100 py-16">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <Sparkles className="mx-auto h-8 w-8 text-emerald-600" />
          <h2 className="mt-4 text-2xl font-bold text-zinc-900">Ready for first value?</h2>
          <p className="mt-3 text-zinc-600">
            Connect HubSpot or Apollo, install the extension, enrich one profile,
            approve one write, open Outcomes.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link
              href={installHref}
              className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-6 py-3 text-sm font-semibold text-white hover:bg-emerald-500"
            >
              {installLabel}
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/get-started"
              className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-800 hover:bg-zinc-50"
            >
              <Link2 className="h-4 w-4" />
              Create a Gravitre account
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
