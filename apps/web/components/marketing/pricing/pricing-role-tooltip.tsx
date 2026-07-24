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
          <span className="inline-flex items-center gap-1 cursor-help border-b border-dashed border-zinc-300">
            {children}
            <Info className="h-3 w-3 text-zinc-400" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs bg-white border-zinc-200 text-zinc-900 p-3 shadow-lg">
          <div className="flex items-start gap-2">
            <div className="h-6 w-6 rounded-md bg-zinc-100 flex items-center justify-center shrink-0 mt-0.5">
              <Icon className="h-3.5 w-3.5 text-zinc-600" />
            </div>
            <div>
              <p className="font-medium text-sm text-zinc-900">{roleData.name}</p>
              <p className="text-xs text-zinc-500 mt-1">{roleData.description}</p>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
