"use client"

import { cn } from "@/lib/utils"
import { EnvironmentBadge } from "./environment-badge"
import { Play, Workflow, Plug, Database } from "lucide-react"

type ContextEntity = "run" | "workflow" | "connector" | "source"

interface SessionItemProps {
  id: string
  title: string
  timestamp: string
  environment: "production" | "staging"
  contextEntity: ContextEntity
  contextName: string
  isActive?: boolean
  onClick?: () => void
}

const entityIcons: Record<ContextEntity, typeof Play> = {
  run: Play,
  workflow: Workflow,
  connector: Plug,
  source: Database,
}

export function SessionItem({
  title,
  timestamp,
  environment,
  contextEntity,
  contextName,
  isActive = false,
  onClick,
}: SessionItemProps) {
  const Icon = entityIcons[contextEntity]

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full flex-col gap-2 rounded-lg border border-transparent p-3 text-left transition-colors",
        isActive
          ? "border-border bg-accent"
          : "hover:bg-accent"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-medium text-foreground line-clamp-1">{title}</h3>
        <span className="shrink-0 text-[10px] text-muted-foreground">{timestamp}</span>
      </div>

      <div className="flex items-center gap-2">
        <EnvironmentBadge environment={environment} />
        <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
          <Icon className="h-3 w-3" />
          <span className="line-clamp-1">{contextName}</span>
        </div>
      </div>
    </button>
  )
}
