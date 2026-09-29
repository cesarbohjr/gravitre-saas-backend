"use client"

import { Shield, Plug, BookOpen, Brain } from "lucide-react"
import { cn } from "@/lib/utils"

type AgentCapabilitiesCardProps = {
  capabilities?: string[]
  permissions?: string[]
  systems?: string[]
  memoryCount?: number
  advisoryOnly?: boolean
  className?: string
}

export function AgentCapabilitiesCard({
  capabilities = [],
  permissions = [],
  systems = [],
  memoryCount,
  advisoryOnly = false,
  className,
}: AgentCapabilitiesCardProps) {
  const reads = capabilities.length > 0 ? capabilities : permissions
  const writes = permissions.filter((entry) => !reads.includes(entry))

  return (
    <section className={cn("space-y-3", className)} aria-labelledby="agent-capabilities-heading">
      <div>
        <h3 id="agent-capabilities-heading" className="text-sm font-semibold text-foreground">
          Capabilities
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          What this agent can access, what actions require approval, and what it has learned.
        </p>
      </div>

      {advisoryOnly ? (
        <p className="border-l-2 border-warning py-1 pl-3 text-xs text-foreground">
          Advisory mode — recommends and analyzes; write actions stay human-gated.
        </p>
      ) : null}

      <div className="grid gap-px border-y border-[color:var(--g-border-default)] bg-[color:var(--g-border-subtle)] sm:grid-cols-2">
        <CapabilityBlock
          icon={BookOpen}
          title="Can read / analyze"
          items={reads}
          empty="No read capabilities configured"
        />
        <CapabilityBlock
          icon={Shield}
          title="Write actions (approval-gated)"
          items={writes}
          empty="No write actions configured"
        />
        <CapabilityBlock
          icon={Plug}
          title="Connectors"
          items={systems}
          empty="No connectors attached — connect tools to unlock actions"
        />
        <CapabilityBlock
          icon={Brain}
          title="Memory"
          items={typeof memoryCount === "number" ? [`${memoryCount} stored memories`] : []}
          empty="Not reported until the agent has run"
        />
      </div>
    </section>
  )
}

function CapabilityBlock({
  icon: Icon,
  title,
  items,
  empty,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  items: string[]
  empty: string
}) {
  return (
    <div className="bg-background px-3 py-3">
      <div className="mb-1.5 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {title}
      </div>
      {items.length > 0 ? (
        <ul className="space-y-1 text-sm text-foreground">
          {items.map((item) => (
            <li key={item} className="text-pretty">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  )
}
