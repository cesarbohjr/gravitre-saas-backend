"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { Suspense } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  FleetPrototypeShell,
  type PrototypeScreen,
} from "@/components/agents/fleet-v4"
import { ShotAuthProvider } from "../shot-auth"

/**
 * Agents 4.0 — high-fidelity prototype gallery (fixture data only).
 * Not linked from production nav. Approve visuals before Phase 1 production.
 */
const PROTOTYPES: { id: string; title: string; blurb: string; screen: PrototypeScreen }[] = [
  {
    id: "1",
    title: "Compact agent identity system",
    blurb: "Tile sizes sm/md/lg + role icons + status dots.",
    screen: "identity",
  },
  {
    id: "2",
    title: "TEAM view",
    blurb: "Ungrouped compact cards — activity over avatar size.",
    screen: "team",
  },
  {
    id: "3",
    title: "Department-grouped TEAM",
    blurb: "Default fleet organization by department.",
    screen: "team-grouped",
  },
  {
    id: "4",
    title: "LIST view",
    blurb: "Dense Nodus table for ops management.",
    screen: "list",
  },
  {
    id: "5",
    title: "GRAPH view (idle)",
    blurb: "Honest edges only: parent, swarm, connector usage.",
    screen: "graph",
  },
  {
    id: "6",
    title: "GRAPH — active multi-agent run",
    blurb: "Live path pulse on swarm parent → subtask edges.",
    screen: "graph-run",
  },
  {
    id: "7",
    title: "Agent inspector",
    blurb: "Canonical detail drawer; Train moved here.",
    screen: "inspector",
  },
  {
    id: "8",
    title: "Icon / color appearance picker",
    blurb: "Curated palette; role-suggested default icon.",
    screen: "picker",
  },
  {
    id: "9",
    title: "Narrow desktop (1024)",
    blurb: "Constrained width TEAM layout.",
    screen: "narrow",
  },
  {
    id: "10",
    title: "Mobile (390)",
    blurb: "LIST default — no unreadable graph.",
    screen: "mobile",
  },
  {
    id: "11",
    title: "Current vs proposed",
    blurb: "Glow orbs beside compact identity tiles.",
    screen: "compare",
  },
]

function Agents4PrototypeBody() {
  const params = useSearchParams()
  const p = params.get("p") ?? "index"

  if (p === "index") {
    return (
      <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
        <div className="space-y-1">
          <h1 className="text-lg font-semibold">Agents 4.0 — prototypes</h1>
          <p className="text-sm text-muted-foreground">
            High-fidelity fixture captures for Nodus-aligned identity + TEAM / LIST / GRAPH. Not
            production. Approve before Phase 1 implementation on{" "}
            <code className="text-xs">/agents</code>.
          </p>
        </div>
        <ul className="divide-y divide-border rounded-xl border border-border/70">
          {PROTOTYPES.map((item) => (
            <li key={item.id}>
              <Link
                href={`/e2e/shots/agents-4?p=${item.id}`}
                className="flex flex-col gap-0.5 px-4 py-3 transition-colors hover:bg-muted/40"
              >
                <span className="text-sm font-medium">
                  {item.id}. {item.title}
                </span>
                <span className="text-xs text-muted-foreground">{item.blurb}</span>
              </Link>
            </li>
          ))}
          <li>
            <Link
              href="/e2e/shots/agents-4?p=shell"
              className="flex flex-col gap-0.5 px-4 py-3 transition-colors hover:bg-muted/40"
            >
              <span className="text-sm font-medium">Interactive shell</span>
              <span className="text-xs text-muted-foreground">
                Switch TEAM / LIST / GRAPH with search + inspector
              </span>
            </Link>
          </li>
          <li>
            <Link
              href="/e2e/shots/agents"
              className="flex flex-col gap-0.5 px-4 py-3 transition-colors hover:bg-muted/40"
            >
              <span className="text-sm font-medium">Production agents shot</span>
              <span className="text-xs text-muted-foreground">
                Live /agents surface with fixture data (TEAM / LIST / GRAPH)
              </span>
            </Link>
          </li>
        </ul>
      </div>
    )
  }

  if (p === "shell") {
    return <FleetPrototypeShell screen="shell" />
  }

  const proto = PROTOTYPES.find((item) => item.id === p)
  if (!proto) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        Unknown prototype. <Link href="/e2e/shots/agents-4">Back to index</Link>
      </div>
    )
  }

  return (
    <div>
      <div className="border-b border-divide px-4 py-2 text-xs text-muted-foreground sm:px-6">
        Prototype {proto.id} — {proto.title}{" "}
        <Link href="/e2e/shots/agents-4" className="ml-2 text-[color:var(--g-brand)]">
          Gallery
        </Link>
      </div>
      <FleetPrototypeShell
        screen={proto.screen}
        forceNarrow={proto.screen === "narrow"}
        forceMobile={proto.screen === "mobile"}
        openInspectorOnMount={proto.screen === "inspector"}
        showExecution={proto.screen === "graph-run"}
      />
    </div>
  )
}

export default function Agents4ShotPage() {
  return (
    <ShotAuthProvider>
      <AppShell title="AI Team — Agents 4.0 Prototypes">
        <Suspense fallback={<p className="p-6 text-sm text-muted-foreground">Loading prototype…</p>}>
          <Agents4PrototypeBody />
        </Suspense>
      </AppShell>
    </ShotAuthProvider>
  )
}
