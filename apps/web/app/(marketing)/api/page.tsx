"use client"

import Link from "next/link"
import { Copy, Check, Play, BookOpen, Webhook, Key } from "lucide-react"
import {
  NucleoApproval,
  NucleoActivity,
  NucleoArrowRight,
  NucleoConnector,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { useState } from "react"
import { DivideX } from "@/components/marketing/nodus/divide"
import {
  MarketingPageEndCta,
  MarketingPageHero,
  MarketingRails,
} from "@/components/marketing/nodus/page-shell"
import {
  API_TRACE_STAGES,
  GravitreFlow,
  GravitreReveal,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  StageTraceVisual,
} from "@/components/marketing/system"

const endpoints = [
  {
    method: "POST",
    path: "/api/workflows/{id}/execute",
    description: "Execute a workflow with optional parameters",
    badge: "Core",
  },
  {
    method: "GET",
    path: "/api/workflows",
    description: "List all workflows with filtering and pagination",
    badge: null,
  },
  {
    method: "GET",
    path: "/api/workflows/{id}/builder",
    description: "Get workflow graph with nodes and edges for the visual builder",
    badge: null,
  },
  {
    method: "POST",
    path: "/api/workflows/{id}/dry-run",
    description: "Preview workflow execution without committing changes",
    badge: "Core",
  },
  {
    method: "GET",
    path: "/api/runs/{id}",
    description: "Get detailed status, steps, and outputs for a run",
    badge: null,
  },
  {
    method: "POST",
    path: "/api/runs/{id}/approve",
    description: "Approve a pending workflow run (human-in-the-loop)",
    badge: null,
  },
  {
    method: "GET",
    path: "/api/admin/intelligence/snapshot",
    description: "Org learning snapshot — query volume, clusters, and knowledge gaps",
    badge: "Intelligence",
  },
  {
    method: "GET",
    path: "/api/connectors",
    description: "List connectors with live Configured → Executable availability",
    badge: null,
  },
  {
    method: "POST",
    path: "/api/connectors/{id}/sync",
    description: "Trigger a manual sync for an integration",
    badge: null,
  },
  {
    method: "GET",
    path: "/api/metrics/overview",
    description: "Get dashboard metrics (workflows, success rate, runs)",
    badge: null,
  },
  {
    method: "POST",
    path: "/api/operator/action-plan",
    description: "Generate an AI action plan from natural language",
    badge: "AI",
  },
]

const sdks = [
  {
    name: "Node.js",
    install: "npm install @gravitre/sdk",
    color: "text-green-600",
    docs: "/docs/api/quickstart",
  },
  {
    name: "Python",
    install: "pip install gravitre",
    color: "text-blue-600",
    docs: "/docs/api/quickstart",
  },
  {
    name: "Go",
    install: "go get github.com/gravitre/go-sdk",
    color: "text-cyan-700",
    docs: "/docs/api/quickstart",
  },
]

const features = [
  {
    icon: NucleoApproval,
    title: "Same approval gates",
    description: "Writes go through the same human approval gates as the product UI",
  },
  {
    icon: NucleoWorkflow,
    title: "Secure by default",
    description: "OAuth 2.0, API keys, and signed webhooks",
  },
  {
    icon: NucleoActivity,
    title: "Auditable runs",
    description: "Runs and approvals show up in the same audit trail operators already review",
  },
  {
    icon: NucleoConnector,
    title: "Live connector health",
    description: "Connector availability matches what you see in the product — Configured → Executable",
  },
]

const codeExample = `import { Gravitre } from '@gravitre/sdk';

const client = new Gravitre({
  apiKey: process.env.GRAVITRE_API_KEY,
  orgId: process.env.GRAVITRE_ORG_ID
});

// Execute a workflow
const run = await client.workflows.execute('wf_lead_sync', {
  parameters: {
    source: 'salesforce',
    destination: 'hubspot',
    syncMode: 'incremental'
  }
});

// Poll for completion or use webhooks
const result = await run.waitForCompletion();

console.log(result.status); // 'completed'
console.log(result.steps);  // Array of step outputs
// [{ name: 'Fetch Data', status: 'completed', output: {...} }, ...]`

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button onClick={copy} className="rounded-lg p-2 transition-colors hover:bg-muted">
      {copied ? (
        <Check className="h-4 w-4 text-emerald-400" />
      ) : (
        <Copy className="h-4 w-4 text-muted-foreground" />
      )}
    </button>
  )
}

export default function APIPage() {
  return (
    <div className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge="REST API v1"
        title={
          <>
            Build with the
            <br />
            <span className="text-brand">Gravitre API</span>
          </>
        }
        description="Execute workflows, query intelligence endpoints, and wire Gravitre into your stack — with the same connector health and approval gates as the product UI."
      >
        <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href="/docs/api/quickstart"
            className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-foreground/90"
          >
            Get Started
            <NucleoArrowRight className="h-4 w-4" />
          </Link>
          <Link
            href="/docs/api/reference"
            className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
          >
            <BookOpen className="h-4 w-4" />
            API Reference
          </Link>
        </div>
      </MarketingPageHero>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="API path"
          title="Auth → Request → Approve → Audit"
          description="One signature TRACE — the same governed path as the product UI, exposed over HTTP."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={API_TRACE_STAGES}
            gradientId="api-trace"
            ariaLabel="API path from auth through request and approve to audit"
            caption="Rate limits are plan-specific and documented in the API docs — ask us for the limits that match your plan. No invented tier numbers here."
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <MarketingRails>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {features.map((feature, i) => {
            const Icon = feature.icon
            return (
              <GravitreFlow
                key={feature.title}
                delay={i * 0.08}
                className="flex items-start gap-4 rounded-xl border border-divide bg-gray-50 p-5"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/15">
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <h3 className="font-medium text-foreground">{feature.title}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">{feature.description}</p>
                </div>
              </GravitreFlow>
            )
          })}
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="mb-12 text-center">
            <h2 className="mb-4 text-3xl font-bold text-foreground">Simple, powerful integration</h2>
            <p className="text-muted-foreground">Execute AI agents with just a few lines of code</p>
          </GravitreReveal>

          <GravitreReveal
            delay={0.08}
            className="relative overflow-hidden rounded-2xl border border-divide bg-foreground"
          >
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="h-3 w-3 rounded-full bg-red-500/80" />
                  <div className="h-3 w-3 rounded-full bg-amber-500/80" />
                  <div className="h-3 w-3 rounded-full bg-primary/80" />
                </div>
                <span className="ml-2 text-xs text-muted-foreground">example.ts</span>
              </div>
              <CopyButton text={codeExample} />
            </div>
            <pre className="overflow-x-auto p-6 text-sm">
              <code className="font-mono text-muted-foreground">
                {codeExample.split("\n").map((line, i) => (
                  <div key={i} className="leading-relaxed">
                    {line.includes("import") && <span className="text-sky-300">{line}</span>}
                    {line.includes("const") && !line.includes("import") && (
                      <span>
                        <span className="text-sky-300">const </span>
                        <span className="text-white">{line.replace("const ", "")}</span>
                      </span>
                    )}
                    {line.includes("await") && (
                      <span>
                        <span className="text-sky-300">await </span>
                        <span className="text-white">{line.replace(/.*await /, "")}</span>
                      </span>
                    )}
                    {line.includes("//") && <span className="text-muted-foreground">{line}</span>}
                    {line.includes("console") && <span className="text-cyan-400">{line}</span>}
                    {!line.includes("import") &&
                      !line.includes("const") &&
                      !line.includes("await") &&
                      !line.includes("//") &&
                      !line.includes("console") && (
                        <span className="text-muted-foreground">{line}</span>
                      )}
                  </div>
                ))}
              </code>
            </pre>
          </GravitreReveal>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="mb-8 flex items-center justify-between">
            <h2 className="text-2xl font-bold text-foreground">API Endpoints</h2>
            <Link
              href="/docs/api/reference"
              className="flex items-center gap-1 text-sm text-primary hover:text-primary"
            >
              Full reference
              <NucleoArrowRight className="h-4 w-4" />
            </Link>
          </GravitreReveal>

          <div className="space-y-3">
            {endpoints.map((endpoint, i) => (
              <GravitreFlow
                key={endpoint.path}
                delay={i * 0.04}
                className="group flex cursor-pointer items-center gap-4 rounded-xl border border-divide bg-gray-50 p-4 transition-colors hover:border-primary/50"
              >
                <span
                  className={`
                  shrink-0 rounded px-2 py-1 font-mono text-xs font-semibold
                  ${endpoint.method === "GET" ? "bg-blue-100 text-blue-600" : "bg-primary/15 text-primary"}
                `}
                >
                  {endpoint.method}
                </span>
                <code className="font-mono text-sm text-foreground">{endpoint.path}</code>
                {endpoint.badge && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                    {endpoint.badge}
                  </span>
                )}
                <span className="ml-auto hidden text-sm text-muted-foreground sm:block">
                  {endpoint.description}
                </span>
              </GravitreFlow>
            ))}
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="mb-12 text-center">
            <h2 className="mb-4 text-3xl font-bold text-foreground">Official SDKs</h2>
            <p className="text-muted-foreground">Type-safe clients for your favorite languages</p>
          </GravitreReveal>

          <div className="grid gap-4 sm:grid-cols-3">
            {sdks.map((sdk, i) => (
              <GravitreFlow
                key={sdk.name}
                delay={i * 0.08}
                className="rounded-xl border border-divide bg-gray-50 p-6"
              >
                <h3 className={`mb-3 text-lg font-semibold ${sdk.color}`}>{sdk.name}</h3>
                <div className="mb-4 flex items-center gap-2 rounded-lg border border-border bg-foreground p-3">
                  <code className="flex-1 truncate font-mono text-xs text-muted-foreground">
                    {sdk.install}
                  </code>
                  <CopyButton text={sdk.install} />
                </div>
                <Link
                  href={sdk.docs}
                  className="flex items-center gap-1 text-sm text-primary hover:text-primary"
                >
                  Documentation
                  <NucleoArrowRight className="h-3 w-3" />
                </Link>
              </GravitreFlow>
            ))}
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-8 lg:grid-cols-2">
            <GravitreFlow className="rounded-2xl border border-divide bg-gray-50 p-8">
              <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl border border-divide bg-white">
                <Webhook className="h-6 w-6 text-charcoal-700" />
              </div>
              <h3 className="mb-3 text-xl font-bold text-foreground">Webhooks</h3>
              <p className="mb-6 text-muted-foreground">
                Receive real-time notifications when runs complete, workflows trigger, or errors
                occur. All webhooks are signed for security.
              </p>
              <Link
                href="/docs/api/webhooks"
                className="inline-flex items-center gap-2 text-charcoal-700 hover:text-foreground"
              >
                Configure webhooks
                <NucleoArrowRight className="h-4 w-4" />
              </Link>
            </GravitreFlow>

            <GravitreFlow delay={0.08} className="rounded-2xl border border-divide bg-gray-50 p-8">
              <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl border border-divide bg-white">
                <Key className="h-6 w-6 text-charcoal-700" />
              </div>
              <h3 className="mb-3 text-xl font-bold text-foreground">Authentication</h3>
              <p className="mb-6 text-muted-foreground">
                Secure API access with scoped API keys or OAuth 2.0. Fine-grained permissions let
                you control exactly what each integration can access.
              </p>
              <Link
                href="/docs/api/authentication"
                className="inline-flex items-center gap-2 text-charcoal-700 hover:text-foreground"
              >
                Authentication guide
                <NucleoArrowRight className="h-4 w-4" />
              </Link>
            </GravitreFlow>
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl text-center">
          <GravitreReveal>
            <h2 className="mb-4 text-3xl font-bold text-foreground">Ready to build?</h2>
            <p className="mb-8 text-muted-foreground">
              Get your API key and start integrating Gravitre in minutes.
            </p>
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/get-started"
                className="inline-flex items-center gap-2 rounded-full bg-primary px-8 py-3 text-sm font-medium text-white transition-colors hover:bg-primary/90"
              >
                Get API Key
                <NucleoArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs/api/quickstart"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-8 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
              >
                <Play className="h-4 w-4" />
                Quickstart Guide
              </Link>
            </div>
          </GravitreReveal>
        </div>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
