"use client"

import { Info } from "lucide-react"
import { roles, type RoleKey } from "@/lib/pricing-page-data"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export function PricingRoleTooltip({
  role,
  children,
}: {
  role: RoleKey
  children: React.ReactNode
}) {
  const roleData = roles[role]
  const Icon = roleData.icon

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center gap-1 cursor-help border-b border-dashed border-border">
            {children}
            <Info className="h-3 w-3 text-muted-foreground" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs bg-card border-border text-foreground p-3 shadow-lg">
          <div className="flex items-start gap-2">
            <div className="h-6 w-6 rounded-md bg-muted flex items-center justify-center shrink-0 mt-0.5">
              <Icon className="h-3.5 w-3.5 text-muted-foreground" />
            </div>
            <div>
              <p className="font-medium text-sm text-foreground">{roleData.name}</p>
              <p className="text-xs text-muted-foreground mt-1">{roleData.description}</p>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
