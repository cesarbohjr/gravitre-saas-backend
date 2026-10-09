"use client"

import Link from "next/link"
import { useState } from "react"
import { toast } from "sonner"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import {
  AgentFleetInspectorBody,
  type AgentFleetInspectorAgent,
} from "@/components/agents/fleet-v4/agent-fleet-inspector"
import { agentsApi } from "@/lib/api"
import {
  DEPARTMENT_BY_ID,
  missingPieces,
  type RosterAgent,
  type RosterGoal,
  type WorkMapModel,
} from "@/lib/agents-roster"
import { cn } from "@/lib/utils"
import { DepartmentIcon } from "@/components/agents/department-icon"
import { giveTaskHref } from "./agent-bits"

/** A node the user clicked on the work map: agent id, app name, output name or goal id. */
export type MapNode = { kind: "agent" | "app" | "out" | "goal"; key: string }

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`
}

function listNames(xs: string[]) {
  return xs.length <= 1 ? xs[0] ?? "" : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border px-5 py-4">
      <h3 className="mb-2 text-xs font-medium text-muted-foreground">{title}</h3>
      {children}
    </section>
  )
}

function AppRow({ name, onOpen }: { name: string; onOpen?: () => void }) {
  const body = (
    <>
      <ConnectorIcon vendor={name} name={name} size="sm" showStatusIndicator={false} />
      <span className="truncate">{name}</span>
    </>
  )
  return onOpen ? (
    <button type="button" onClick={onOpen} className="flex w-full items-center gap-2.5 rounded-md px-1.5 py-1.5 text-left text-sm text-foreground hover:bg-muted">
      {body}
    </button>
  ) : (
    <div className="flex items-center gap-2.5 px-1.5 py-1.5 text-sm text-foreground">{body}</div>
  )
}

function AgentRow({ agent, onOpen }: { agent: RosterAgent; onOpen: () => void }) {
  const dept = DEPARTMENT_BY_ID.get(agent.department)?.name ?? agent.departmentLabel
  return (
    <button type="button" onClick={onOpen} className="flex w-full items-center justify-between gap-3 rounded-md px-1.5 py-1.5 text-left hover:bg-muted">
      <DepartmentIcon department={agent.department} size="sm" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{agent.name}</span>
        <span className="block truncate text-xs text-muted-foreground">{[dept, agent.role].filter(Boolean).join(" · ")}</span>
      </span>
      <span className="shrink-0 text-xs text-muted-foreground">{agent.tasksToday > 0 ? `${agent.tasksToday} today` : stateLabel(agent)}</span>
    </button>
  )
}

function stateLabel(agent: RosterAgent) {
  switch (agent.state) {
    case "working":
      return "Working"
    case "active_today":
      return "Active today"
    case "blocked":
      return "Blocked"
    case "not_set_up":
      return "Not set up"
    default:
      return "Ready"
  }
}

function GoalLink({ goal }: { goal: RosterGoal }) {
  return (
    <Link href={`/goals/${encodeURIComponent(goal.id)}`} className="block rounded-md px-1.5 py-1.5 text-sm text-foreground hover:bg-muted">
      {goal.objective || "Untitled goal"}
      <span className="block text-xs text-muted-foreground capitalize">{goal.status}</span>
    </Link>
  )
}

function toInspectorAgent(agent: RosterAgent, raw: Record<string, unknown> | undefined): AgentFleetInspectorAgent {
  const rawStats = (raw?.stats ?? null) as Partial<AgentFleetInspectorAgent["stats"]> | null
  return {
    ...(raw as Partial<AgentFleetInspectorAgent>),
    id: agent.id,
    name: agent.name,
    role: agent.role || String(raw?.role ?? ""),
    department: String(raw?.department ?? agent.departmentLabel),
    description: agent.description,
    status: agent.status,
    model: agent.model !== "default" ? agent.model : null,
    capabilities: agent.capabilities,
    connectedSystems: agent.apps,
    stats: {
      // Job stats (what the map shows) win over the agents API's own counters.
      tasksToday: agent.stats ? agent.tasksToday : statsNumber(rawStats?.tasksToday) ?? agent.tasksToday,
      successRate: agent.stats ? agent.success7d : statsNumber(rawStats?.successRate) ?? agent.success7d,
      avgResponseTime: typeof rawStats?.avgResponseTime === "string" ? rawStats.avgResponseTime : "",
      workflowsUsing: statsNumber(rawStats?.workflowsUsing) ?? 0,
    },
  }
}

function statsNumber(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null
}

/**
 * Detail sheet for any node on the work map. Agents reuse the fleet inspector the
 * graph opened before the redesign; apps, outputs and goals get the same shape.
 */
export function RosterNodeSheet({
  node,
  onOpenChange,
  onOpenNode,
  model,
  wired,
  rawById,
  onChanged,
}: {
  node: MapNode | null
  onOpenChange: (open: boolean) => void
  onOpenNode: (node: MapNode) => void
  /** The model over every agent, so dormant agents' details are complete too. */
  model: WorkMapModel
  wired: Set<string>
  rawById?: Map<string, Record<string, unknown>>
  onChanged?: () => Promise<unknown> | void
}) {
  const [busy, setBusy] = useState(false)
  const byId = new Map(model.agents.map((a) => [a.id, a]))
  const goalsFor = (agentId: string) => model.goals.filter((g) => (model.goalAgents.get(g.id) ?? []).includes(agentId))

  async function act(label: string, fn: () => Promise<unknown>) {
    setBusy(true)
    try {
      await fn()
      await onChanged?.()
      toast.success(label)
    } catch {
      toast.error("That did not go through. Try again.")
    } finally {
      setBusy(false)
    }
  }

  let title = ""
  let description = ""
  let body: React.ReactNode = null

  if (node?.kind === "agent") {
    const agent = byId.get(node.key)
    if (agent) {
      title = agent.name
      description = agent.role || agent.departmentLabel
      const goals = goalsFor(agent.id)
      const missing = missingPieces(agent, model)
      const isWired = wired.has(agent.id)
      const inspector = toInspectorAgent(agent, rawById?.get(agent.id))
      body = (
        <>
          <AgentFleetInspectorBody
            agent={inspector}
            layout="sheet"
            isMutating={busy}
            successRateDisplay={inspector.stats.successRate}
            onStart={(a) => act(`${a.name} is active`, () => agentsApi.start(a.id))}
            onStop={(a) => act(`${a.name} is paused`, () => agentsApi.stop(a.id))}
            onDepartmentChange={(id, department) =>
              void act(`${agent.name} moved to ${department}`, () => agentsApi.update(id, { department }))
            }
          />
          <Section title="On the work map">
            {isWired ? (
              <p className="text-sm text-foreground">Fully connected. Its work flows from its apps into {plural(goals.length, "goal")}.</p>
            ) : (
              <p className="text-sm text-foreground">
                Dormant. It still needs {listNames(missing)} before its work shows up on the map.
              </p>
            )}
          </Section>
          <Section title="Reads from">
            {agent.apps.length ? (
              agent.apps.map((app) => <AppRow key={app} name={app} onOpen={() => onOpenNode({ kind: "app", key: app })} />)
            ) : (
              <Link href="/connectors" className="text-sm font-medium text-[color:var(--g-brand)]">
                Connect an app
              </Link>
            )}
          </Section>
          <Section title="Produces">
            {agent.output ? (
              <button type="button" onClick={() => onOpenNode({ kind: "out", key: agent.output as string })} className="text-sm font-medium text-foreground hover:underline">
                {agent.output}
              </button>
            ) : (
              <p className="text-sm text-muted-foreground">No output yet. Give it instructions that say what it delivers.</p>
            )}
          </Section>
          <Section title="Counts toward">
            {goals.length ? goals.map((g) => <GoalLink key={g.id} goal={g} />) : <p className="text-sm text-muted-foreground">No goal yet.</p>}
          </Section>
        </>
      )
    }
  } else if (node?.kind === "app") {
    const app = model.apps.find((p) => p.name === node.key)
    const users = (app?.agentIds ?? []).map((id) => byId.get(id)).filter((a): a is RosterAgent => Boolean(a))
    const goals = model.goals.filter((g) => g.connectedSystems.some((s) => s.toLowerCase() === node.key.toLowerCase()) || users.some((u) => (model.goalAgents.get(g.id) ?? []).includes(u.id)))
    title = node.key
    description = `Connector · ${plural(users.length, "agent")} use it`
    body = (
      <>
        <div className="flex items-center gap-3 px-5 pb-4 pt-5 pr-12">
          <ConnectorIcon vendor={node.key} name={node.key} size="md" showStatusIndicator={false} />
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-foreground">{node.key}</h2>
            <p className="text-[13px] text-muted-foreground">{description}</p>
          </div>
        </div>
        <Section title="Agents that use it">
          {users.length ? users.map((a) => <AgentRow key={a.id} agent={a} onOpen={() => onOpenNode({ kind: "agent", key: a.id })} />) : <p className="text-sm text-muted-foreground">No agent uses it yet.</p>}
        </Section>
        <Section title="Goals it supports">
          {goals.length ? goals.map((g) => <GoalLink key={g.id} goal={g} />) : <p className="text-sm text-muted-foreground">No goal relies on it yet.</p>}
        </Section>
        <div className="px-5 py-4">
          <Link href="/connectors" className="inline-flex h-9 items-center rounded-md border border-border px-3 text-sm font-medium text-foreground hover:bg-muted">
            Manage in Connectors
          </Link>
        </div>
      </>
    )
  } else if (node?.kind === "out") {
    const out = model.outputs.find((o) => o.name === node.key)
    const owners = (out?.agentIds ?? []).map((id) => byId.get(id)).filter((a): a is RosterAgent => Boolean(a))
    const goals = model.goals.filter((g) => out?.goalIds.includes(g.id))
    const apps = [...new Set(owners.flatMap((a) => a.apps))]
    const done = owners.reduce((s, a) => s + a.tasksToday, 0)
    title = node.key
    description = "Workflow output"
    body = (
      <>
        <div className="px-5 pb-4 pt-5 pr-12">
          <p className="text-xs font-medium text-muted-foreground">Workflow output</p>
          <h2 className="mt-1 text-base font-semibold text-foreground">{node.key}</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            {done > 0 ? `${plural(done, "task")} finished today` : "No tasks finished today"}
            {out?.gated ? " · Writes wait for your approval" : ""}
          </p>
        </div>
        <Section title="Produced by">
          {owners.map((a) => (
            <AgentRow key={a.id} agent={a} onOpen={() => onOpenNode({ kind: "agent", key: a.id })} />
          ))}
        </Section>
        <Section title="Uses data from">
          {apps.length ? apps.map((app) => <AppRow key={app} name={app} onOpen={() => onOpenNode({ kind: "app", key: app })} />) : <p className="text-sm text-muted-foreground">No connected app.</p>}
        </Section>
        <Section title="Counts toward">
          {goals.length ? goals.map((g) => <GoalLink key={g.id} goal={g} />) : <p className="text-sm text-muted-foreground">Not tied to a goal, so nothing measures it yet.</p>}
        </Section>
        {out?.gated ? (
          <div className="px-5 py-4">
            <Link href="/approvals" className="inline-flex h-9 items-center rounded-md border border-border px-3 text-sm font-medium text-foreground hover:bg-muted">
              Open decision queue
            </Link>
          </div>
        ) : null}
      </>
    )
  } else if (node?.kind === "goal") {
    const goal = model.goals.find((g) => g.id === node.key)
    if (goal) {
      const feeders = (model.goalAgents.get(goal.id) ?? []).map((id) => byId.get(id)).filter((a): a is RosterAgent => Boolean(a))
      const systems = goal.connectedSystems
      const working = feeders.filter((a) => a.state === "working" || a.state === "active_today").length
      const blocked = feeders.filter((a) => a.state === "blocked").length
      title = goal.objective || "Untitled goal"
      description = [goal.status, goal.department, goal.priority ? `${goal.priority} priority` : null].filter(Boolean).join(" · ")
      body = (
        <>
          <div className="px-5 pb-4 pt-5 pr-12">
            <p className="text-xs font-medium text-muted-foreground">Goal</p>
            <h2 className="mt-1 text-base font-semibold text-foreground">{title}</h2>
            <p className="mt-1 text-[13px] capitalize text-muted-foreground">{description}</p>
          </div>
          <dl className="grid grid-cols-3 gap-3 border-t border-border px-5 py-4 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">Agents</dt>
              <dd className="tabular-nums text-foreground">{feeders.length}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Working today</dt>
              <dd className="tabular-nums text-foreground">{working}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Blocked</dt>
              <dd className="tabular-nums text-foreground">{blocked}</dd>
            </div>
          </dl>
          <Section title="Agents feeding it">
            {feeders.length ? feeders.map((a) => <AgentRow key={a.id} agent={a} onOpen={() => onOpenNode({ kind: "agent", key: a.id })} />) : <p className="text-sm text-muted-foreground">No agent feeds it yet.</p>}
          </Section>
          <Section title="Connected tools">
            {systems.length ? systems.map((s) => <AppRow key={s} name={s} />) : <p className="text-sm text-muted-foreground">No tools picked for this goal.</p>}
          </Section>
          <div className="px-5 py-4">
            <Link href={`/goals/${encodeURIComponent(goal.id)}`} className="inline-flex h-9 items-center rounded-md bg-foreground px-3 text-sm font-medium text-background hover:opacity-90">
              Open goal
            </Link>
          </div>
        </>
      )
    }
  }

  const agentNode = node?.kind === "agent" ? byId.get(node.key) : undefined
  return (
    <Sheet open={Boolean(node && body)} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 overflow-y-auto p-0 sm:max-w-[420px]">
        <SheetHeader className="sr-only">
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>{description}</SheetDescription>
        </SheetHeader>
        <div className={cn(node?.kind === "agent" && "pb-2")}>{body}</div>
        {agentNode ? (
          <div className="border-t border-border px-5 py-4">
            <Link href={giveTaskHref(agentNode.id)} className="inline-flex h-9 items-center rounded-md bg-foreground px-3 text-sm font-medium text-background hover:opacity-90">
              Give {agentNode.name} a task
            </Link>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
