"use client"

import { motion } from "framer-motion"
import {
  NucleoApproval,
  NucleoChat,
  NucleoCommand,
  NucleoConnector,
  NucleoHistory,
  NucleoRun,
  NucleoSearch,
  NucleoSuccess,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { MOTION, TYPE } from "@/lib/design-system"
import { useMotionPrefs } from "@/lib/animations"

export function SelectedNucleo({ scene }: { scene: string }) {
  const sizes = [
    [14, "row / table"],
    [16, "default"],
    [18, "secondary"],
    [20, "composer"],
    [24, "identity / graph"],
  ] as const
  const icons = [
    ["Ask", NucleoChat],
    ["Command", NucleoCommand],
    ["Run", NucleoRun],
    ["Connector", NucleoConnector],
    ["Evidence", NucleoHistory],
    ["Relationship", NucleoSearch],
    ["Workflow", NucleoWorkflow],
    ["Approval", NucleoApproval],
  ] as const
  return (
    <div data-review-surface="nucleo" data-review-scene={scene} className="max-w-3xl">
      <p className={TYPE.eyebrow}>Nucleo Sharp 24 Outline · locked</p>
      <p className={cn(TYPE.pageLead, "mt-2")}>
        Function, not sparkle. No AiOutline24 / sparkle / brain / wand as Gravitre identity. Agent roles use department
        function marks — not cartoon faces.
      </p>
      <div className="mt-6 grid gap-4">
        {icons.map(([label, Icon]) => (
          <div key={label} className="flex items-center gap-6 border-b border-[color:var(--g-border-subtle)] py-3">
            <span className="w-24 text-sm">{label}</span>
            {sizes.map(([size]) => (
              <Icon key={size} size={size} />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function SelectedConnectors({ scene }: { scene: string }) {
  const empty = scene.includes("empty")
  const loading = scene.includes("loading")
  const error = scene.includes("error")
  const selected = scene.includes("selected")
  return (
    <div data-review-surface="connectors" data-review-scene={scene} className="max-w-2xl">
      <h2 className={TYPE.sectionTitle}>Discover → manage</h2>
      {loading && <p className={cn(TYPE.meta, "mt-4")}>Checking live status…</p>}
      {error && <p className="mt-4 text-sm text-[color:var(--g-danger)]">Could not refresh health.</p>}
      {empty && !loading && (
        <p className={cn(TYPE.bodyMuted, "mt-4")}>No connectors yet. Start from available providers.</p>
      )}
      {!empty && !loading && (
        <>
          <p className={cn(TYPE.eyebrow, "mt-6")}>Available</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {["Apollo", "GitHub", "Notion"].map((name) => (
              <span
                key={name}
                className="inline-flex items-center gap-2 border border-[color:var(--g-border-default)] px-3 py-1.5 text-sm"
              >
                <span className="flex h-4 w-4 items-center justify-center bg-[color:var(--g-surface-3)] text-[10px]">
                  {name[0]}
                </span>
                {name}
              </span>
            ))}
          </div>
          <p className={cn(TYPE.eyebrow, "mt-6")}>Connected</p>
          <ul>
            {[
              ["HubSpot", "token 2d"],
              ["Slack", "healthy"],
              ["Salesforce", "healthy"],
            ].map(([name, health]) => (
              <li
                key={name}
                className={cn(
                  "flex items-center justify-between border-b border-[color:var(--g-border-subtle)] py-2.5 text-sm",
                  selected && name === "HubSpot" && "bg-[color:var(--g-surface-active)]",
                )}
              >
                <span className="inline-flex items-center gap-2">
                  <NucleoConnector size={16} />
                  {name}
                </span>
                <span className={TYPE.meta}>{health} · sync 4m</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

function RoleMark({ kind }: { kind: "sales" | "support" | "ops" }) {
  const Icon = kind === "sales" ? NucleoRun : kind === "support" ? NucleoApproval : NucleoWorkflow
  return (
    <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center border border-[color:var(--g-border-default)]">
      <Icon size={16} />
    </span>
  )
}

const TEAM = [
  { dept: "Sales", kind: "sales" as const, name: "Inbound Lead Triage", spec: "Router", state: "routing inbound", act: "assigned AE · 4m" },
  { dept: "Sales", kind: "sales" as const, name: "Deal Desk Brief", spec: "Analyst", state: "idle", act: "briefed ACME · 1h" },
  { dept: "Support", kind: "support" as const, name: "Ticket Summarizer", spec: "Ops", state: "idle", act: "closed 12 · 22m" },
  { dept: "Operations", kind: "ops" as const, name: "Connector Watch", spec: "Watch", state: "watching", act: "HubSpot token 2d" },
]

export function SelectedAgents({ scene }: { scene: string }) {
  const view = scene.includes("list") ? "list" : scene.includes("graph") ? "graph" : "team"
  const selected = scene.includes("selected")
  const empty = scene.includes("empty")
  const mobile = scene.includes("mobile")
  const prefs = useMotionPrefs()
  const depts = [...new Set(TEAM.map((t) => t.dept))]
  return (
    <div
      data-review-surface="agents"
      data-review-scene={scene}
      className={cn(mobile && "mx-auto max-w-[390px]")}
    >
      <p className={TYPE.eyebrow}>One Intelligence Core · operating team</p>
      <div className="mb-4 mt-2 flex gap-3 text-sm">
        <span className={view === "team" ? "font-medium" : "text-[color:var(--g-text-muted)]"}>Team</span>
        <span className={view === "list" ? "font-medium" : "text-[color:var(--g-text-muted)]"}>List</span>
        <span className={view === "graph" ? "font-medium" : "text-[color:var(--g-text-muted)]"}>Graph</span>
      </div>
      {empty && <p className={TYPE.bodyMuted}>No teammates in this department yet.</p>}
      {!empty && view === "team" && (
        <div className="grid gap-8 md:grid-cols-2">
          {depts.map((dept) => (
            <section key={dept}>
              <p className={TYPE.eyebrow}>{dept}</p>
              <ul className="mt-3 space-y-3">
                {TEAM.filter((t) => t.dept === dept).map((t) => (
                  <li
                    key={t.name}
                    className={cn(
                      "flex items-start gap-3 py-2",
                      selected && t.name === "Inbound Lead Triage" && "bg-[color:var(--g-surface-active)]",
                    )}
                  >
                    <RoleMark kind={t.kind} />
                    <div>
                      <p className={TYPE.cardTitle}>{t.name}</p>
                      <p className={TYPE.meta}>
                        {t.spec} · {t.state} · {t.act}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
      {!empty && view === "list" && (
        <ul className="text-sm">
          {TEAM.map((t) => (
            <li key={t.name} className="flex justify-between gap-3 border-b border-[color:var(--g-border-subtle)] py-2">
              <span className="inline-flex items-center gap-2">
                <RoleMark kind={t.kind} />
                {t.name}
              </span>
              <span className={TYPE.meta}>
                {t.dept} · {t.state}
              </span>
            </li>
          ))}
        </ul>
      )}
      {!empty && view === "graph" && (
        <div>
          <p className={TYPE.meta}>Delegation / collaboration — not separate intelligence cores.</p>
          <svg viewBox="0 0 420 180" className="mt-4 w-full max-w-lg" aria-label="Delegation">
            <motion.line
              x1="90"
              y1="90"
              x2="210"
              y2="50"
              stroke="var(--g-signal)"
              initial={prefs.reduced ? false : { pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: MOTION.slow }}
            />
            <line x1="90" y1="90" x2="210" y2="130" stroke="var(--g-border-default)" />
            <circle cx="70" cy="90" r="22" fill="var(--g-canvas)" stroke="currentColor" />
            <circle cx="230" cy="50" r="18" fill="var(--g-canvas)" stroke="currentColor" />
            <circle cx="230" cy="130" r="18" fill="var(--g-canvas)" stroke="currentColor" />
            <text x="70" y="94" textAnchor="middle" fontSize="9">
              Triage
            </text>
            <text x="230" y="54" textAnchor="middle" fontSize="9">
              Desk
            </text>
            <text x="230" y="134" textAnchor="middle" fontSize="9">
              Watch
            </text>
          </svg>
        </div>
      )}
    </div>
  )
}

export function SelectedRelationships({ scene }: { scene: string }) {
  const showEvidence = scene.includes("selected") || scene.includes("inspect")
  const graphOk = !scene.includes("empty") && !scene.includes("loading") && !scene.includes("error")
  return (
    <div
      data-review-surface="relationships"
      data-review-scene={scene}
      className={cn("grid gap-4", showEvidence && "lg:grid-cols-[1fr_280px]")}
    >
      <div className="min-h-[280px] border border-[color:var(--g-border-default)] p-4">
        <div className="mb-3 flex flex-wrap gap-2 text-xs text-[color:var(--g-text-muted)]">
          <span>Search</span>
          <span>Focus</span>
          <span>Filter</span>
          <span>Zoom / pan</span>
          <span>Pin</span>
          <span>Neighborhood</span>
          <span>Path</span>
        </div>
        {scene.includes("loading") && <p className={TYPE.meta}>Loading graph…</p>}
        {scene.includes("empty") && <p className={TYPE.bodyMuted}>No relationships in this filter.</p>}
        {scene.includes("error") && <p className="text-sm text-[color:var(--g-danger)]">Graph failed to load.</p>}
        {graphOk && (
          <svg viewBox="0 0 400 200" className="w-full">
            <line x1="140" y1="100" x2="260" y2="100" stroke="var(--g-signal)" strokeWidth="2" />
            <line x1="120" y1="100" x2="80" y2="40" stroke="var(--g-border-default)" />
            <circle cx="120" cy="100" r="22" fill="var(--g-canvas)" stroke="var(--g-brand)" />
            <circle cx="280" cy="100" r="16" fill="var(--g-canvas)" stroke="currentColor" />
            <circle cx="70" cy="36" r="12" fill="var(--g-canvas)" stroke="currentColor" />
            <text x="120" y="104" textAnchor="middle" fontSize="10">
              Acme
            </text>
            <text x="280" y="104" textAnchor="middle" fontSize="10">
              Sarah
            </text>
            <text x="70" y="40" textAnchor="middle" fontSize="8">
              HubSpot
            </text>
          </svg>
        )}
      </div>
      {showEvidence && graphOk ? (
        <aside className="border border-[color:var(--g-border-active)] bg-[color:var(--g-surface-active)] p-3 text-sm">
          <p className={TYPE.eyebrow}>Evidence</p>
          <p className="mt-2">Acme employs Sarah (AE).</p>
          <ul className={cn(TYPE.meta, "mt-3 space-y-1")}>
            <li>Meaning: employment / ownership</li>
            <li>Source: HubSpot contact owner</li>
            <li>Provenance: CRM sync 2h ago</li>
            <li>Confidence: high · confirmed (not learned-only)</li>
            <li>Freshness: 2h</li>
            <li>Observation: last meeting logged Tue</li>
            <li>Impact: inbound routes to this AE</li>
          </ul>
        </aside>
      ) : (
        graphOk && <p className={TYPE.meta}>Select a node or edge — inspector stays closed until then.</p>
      )}
    </div>
  )
}

export function SelectedPerformance({ scene }: { scene: string }) {
  return (
    <div data-review-surface="performance" data-review-scene={scene} className="max-w-3xl">
      <p className={TYPE.eyebrow}>Outcome</p>
      <h2 className={cn(TYPE.sectionTitle, "mt-1")}>Lead routed · HubSpot 1842</h2>
      {scene.includes("empty") && <p className={cn(TYPE.bodyMuted, "mt-4")}>No diagnostic data for this window.</p>}
      {scene.includes("error") && <p className="mt-4 text-sm text-[color:var(--g-danger)]">Attribution unavailable.</p>}
      {scene.includes("loading") && <p className={cn(TYPE.meta, "mt-4")}>Loading contributing stages…</p>}
      {!scene.includes("empty") && !scene.includes("error") && !scene.includes("loading") && (
        <div className="mt-6 grid gap-6 md:grid-cols-[200px_1fr]">
          <ul className="space-y-2 text-sm">
            {["CRM read", "Policy check", "HubSpot write", "Slack notify"].map((s, i) => (
              <li key={s} className={i === 2 ? "font-medium text-[color:var(--g-brand)]" : ""}>
                {s}
              </li>
            ))}
          </ul>
          <div>
            <p className={TYPE.eyebrow}>Selected span · HubSpot write</p>
            <p className={cn(TYPE.body, "mt-2")}>
              contacts.update owner_id. Instrumented duration 840ms. Outcome: contact 1842 assigned.
            </p>
            <div className="mt-4 space-y-1">
              <div className="h-3 w-2/3 bg-[color:var(--g-surface-3)]" />
              <div className="h-3 w-1/2 bg-[color:var(--g-surface-3)]" />
            </div>
            <p className={cn(TYPE.meta, "mt-3")}>Waterfall is subordinate. Stages shown only if instrumented.</p>
          </div>
        </div>
      )}
    </div>
  )
}

export function SelectedWorkflows({ scene }: { scene: string }) {
  const inspect = scene.includes("selected")
  return (
    <div data-review-surface="workflows" data-review-scene={scene}>
      <p className={TYPE.eyebrow}>Intent</p>
      <h2 className={cn(TYPE.sectionTitle, "mt-1")}>Route inbound leads without dropping CRM fields.</h2>
      {scene.includes("empty") && <p className={cn(TYPE.bodyMuted, "mt-4")}>Canvas has no steps yet.</p>}
      {scene.includes("error") && <p className="mt-4 text-sm text-[color:var(--g-danger)]">Workflow failed to load.</p>}
      {!scene.includes("empty") && !scene.includes("error") && (
        <div className="mt-6 flex flex-wrap items-center gap-3">
          {["Trigger", "Triage", "CRM write", "Notify"].map((n, i) => (
            <span
              key={n}
              className={cn(
                "inline-flex items-center gap-2 border px-3 py-2 text-sm",
                i === 1 ? "border-[color:var(--g-brand)]" : "border-[color:var(--g-border-default)]",
              )}
            >
              <NucleoWorkflow size={16} />
              {n}
              {i === 1 && <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--g-brand)]" />}
            </span>
          ))}
        </div>
      )}
      {inspect && (
        <aside className="mt-6 max-w-sm border border-[color:var(--g-border-active)] p-3 text-sm">
          <p className={TYPE.eyebrow}>Inspect · Triage</p>
          <p className="mt-2">Filter: country = US. Deterministic. Not hidden behind Ask.</p>
        </aside>
      )}
    </div>
  )
}

export function SelectedRuns({ scene }: { scene: string }) {
  const trace = scene.includes("trace")
  return (
    <div data-review-surface="runs" data-review-scene={scene} className="max-w-xl">
      <p className={TYPE.eyebrow}>Outcome</p>
      <h2 className={cn(TYPE.sectionTitle, "mt-1")}>Lead routed to AE</h2>
      {scene.includes("empty") && <p className={cn(TYPE.bodyMuted, "mt-4")}>No runs in this filter.</p>}
      {scene.includes("error") && <p className="mt-4 text-sm text-[color:var(--g-danger)]">Run failed before outcome.</p>}
      {scene.includes("loading") && <p className={cn(TYPE.meta, "mt-4")}>Loading run…</p>}
      {!scene.includes("empty") && !scene.includes("loading") && (
        <ul className="mt-4 space-y-2 text-sm">
          <li className="inline-flex items-center gap-2">
            <NucleoSuccess size={16} /> Terminal: completed
          </li>
          <li>Systems: HubSpot, Slack</li>
          <li>Actions: owner assigned, channel notified</li>
          <li>Output: contact 1842 assigned</li>
          <li>Recoveries: none</li>
        </ul>
      )}
      {trace && (
        <div className="mt-6 space-y-2">
          <p className={TYPE.eyebrow}>Trace</p>
          <div className="h-4 w-1/3 bg-[color:var(--g-surface-3)]" />
          <div className="h-4 w-2/3 bg-[color:var(--g-surface-3)]" />
          <div className="h-4 w-1/2 bg-[color:var(--g-surface-3)]" />
        </div>
      )}
    </div>
  )
}
