"use client"

import { ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"

const PERSONA_OPTIONS = [
  { key: "friendly_assistant", label: "Friendly Assistant" },
  { key: "executive_strategist", label: "Executive Strategist" },
  { key: "sales_advisor", label: "Sales Advisor" },
  { key: "marketing_operator", label: "Marketing Operator" },
  { key: "operations_analyst", label: "Operations Analyst" },
  { key: "support_specialist", label: "Support Specialist" },
  { key: "finance_analyst", label: "Finance Analyst" },
  { key: "engineering_copilot", label: "Engineering Copilot" },
  { key: "deep_research_analyst", label: "Deep Research Analyst" },
] as const

export function PersonaSelector({
  value,
  onChange,
  disabled,
}: {
  value: string
  onChange: (personaKey: string) => void
  disabled?: boolean
}) {
  const label = PERSONA_OPTIONS.find((option) => option.key === value)?.label ?? "Friendly Assistant"

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          className="h-8 gap-1 rounded-full border-border bg-background px-3 text-xs font-medium text-foreground"
        >
          {label}
          <ChevronDown className="h-3 w-3 opacity-60" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-52">
        {PERSONA_OPTIONS.map((option) => (
          <DropdownMenuItem
            key={option.key}
            className={cn("text-xs", value === option.key && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300")}
            onClick={() => onChange(option.key)}
          >
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
