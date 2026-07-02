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
    <section
      className={cn(
        "rounded-2xl border border-border/70 bg-card/40 p-5 space-y-4",
        className,
      )}
    >
      <div>
        <h3 className="text-sm font-semibold text-foreground">Capabilities</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          What this agent can access, what actions require approval, and what it has learned.
        </p>
      </div>

      {advisoryOnly ? (
        <p className="rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          Advisory mode — recommends and analyzes; write actions stay human-gated.
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <CapabilityBlock
          icon={BookOpen}
          title="Can read / analyze"
          items={reads.length > 0 ? reads : ["Org context", "Connected systems", "Internal knowledge"]}
        />
        <CapabilityBlock
          icon={Shield}
          title="Write actions (approval-gated)"
          items={
            writes.length > 0
              ? writes
              : ["Connector writes require approval per org policy"]
          }
        />
        <CapabilityBlock
          icon={Plug}
          title="Connectors"
          items={systems.length > 0 ? systems : ["Connect tools to unlock connector actions"]}
        />
        <CapabilityBlock
          icon={Brain}
          title="Memory"
          items={[
            typeof memoryCount === "number"
              ? `${memoryCount} stored memories`
              : "Memory count available after first runs",
          ]}
        />
      </div>
    </section>
  )
}

function CapabilityBlock({
  icon: Icon,
  title,
  items,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  items: string[]
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-background/50 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {title}
      </div>
      <ul className="space-y-1 text-sm text-foreground">
        {items.map((item) => (
          <li key={item} className="text-pretty">{item}</li>
        ))}
      </ul>
    </div>
  )
}
