"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  ArrowRight,
  CheckCircle2,
  Chrome,
  Link2,
  ListChecks,
  Shield,
  Sparkles,
} from "lucide-react"
import {
  extensionInstallCtaLabel,
  extensionInstallHref,
  hasChromeWebStoreListing,
} from "@/lib/extension-install"

const activationSteps = [
  {
    n: "1",
    title: "Install",
    body: "Add the Gravitree extension in Chrome (store listing when published, or load-unpacked beta).",
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

const surfaces = [
  "LinkedIn profiles",
  "Gmail",
  "Outlook on the web",
  "Company websites (when you invoke Enrich)",
] as const

export function ExtensionPage() {
  const installHref = extensionInstallHref()
  const installLabel = extensionInstallCtaLabel()
  const storeLive = hasChromeWebStoreListing()

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
                Chrome extension · overlay and approve
              </span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl text-balance">
              Enrich the page. Approve the write.{" "}
              <span className="bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent">
                Same Outcomes as chat.
              </span>
            </h1>
            <p className="mx-auto mt-5 max-w-2xl text-lg text-zinc-600">
              Gravitree on LinkedIn, Gmail, Outlook, and company sites — catalog
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
            {!storeLive ? (
              <p className="mt-4 text-sm text-zinc-500">
                Chrome Web Store listing not published yet — use the setup guide
                for the installable Chrome beta (load unpacked).
              </p>
            ) : null}
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

      <section className="border-t border-zinc-100 bg-zinc-50/60 py-16">
        <div className="mx-auto grid max-w-5xl gap-10 px-6 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-bold text-zinc-900">Supported surfaces</h2>
            <p className="mt-3 text-zinc-600">
              Explicit host allowlist — no silent expansion. Page context only;
              creates and list membership use Apollo / HubSpot catalog actions
              when those connectors are connected.
            </p>
            <ul className="mt-6 space-y-3">
              {surfaces.map((s) => (
                <li key={s} className="flex items-start gap-2 text-zinc-800">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                  <span>{s}</span>
                </li>
              ))}
            </ul>
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
              Create a Gravitree account
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
