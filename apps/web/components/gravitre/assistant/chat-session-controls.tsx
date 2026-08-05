"use client"

/**
 * Chat session controls — department · persona · speed.
 *
 * Desktop (handoff 5a/5b): one consolidated trigger
 *   "Support · Friendly Assistant | FAST ▾"
 * Mobile (handoff 4*): chip row — Support ▾ · FAST · Friendly Assistant ▾
 */

import { Check, ChevronDown } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { DEPARTMENT_OPTIONS } from "@/lib/department-context"
import {
  CHAT_PERSONA_OPTIONS,
  resolveChatPersonaLabel,
} from "@/lib/chat-personas"

type ChatSpeed = "fast" | "deep"

type ChatSessionControlsProps = {
  department: string
  onDepartmentChange: (value: string) => void
  persona: string
  onPersonaChange: (value: string) => void
  personaDisabled?: boolean
  chatMode: ChatSpeed
  onChatModeChange: (value: ChatSpeed) => void
  className?: string
}

function departmentLabel(id: string): string {
  return DEPARTMENT_OPTIONS.find((o) => o.id === id)?.label ?? id
}

function ChipTrigger({
  children,
  className,
  "aria-label": ariaLabel,
}: {
  children: React.ReactNode
  className?: string
  "aria-label": string
}) {
  return (
    <DropdownMenuTrigger
      className={cn(
        "inline-flex h-8 shrink-0 items-center gap-1 rounded-full border border-border bg-background px-2.5 text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground sm:h-7 sm:rounded-md sm:text-[11px]",
        className,
      )}
      aria-label={ariaLabel}
    >
      {children}
      <ChevronDown className="h-3 w-3 opacity-60" aria-hidden />
    </DropdownMenuTrigger>
  )
}

export function ChatSessionControls({
  department,
  onDepartmentChange,
  persona,
  onPersonaChange,
  personaDisabled,
  chatMode,
  onChatModeChange,
  className,
}: ChatSessionControlsProps) {
  const dept = departmentLabel(department)
  const personaLabel = resolveChatPersonaLabel(persona)
  const speedLabel = chatMode === "deep" ? "Agent" : "Fast"

  return (
    <div className={cn("flex min-w-0 items-center gap-1.5", className)}>
      {/* Desktop — single consolidated control (handoff 5a/5b) */}
      <DropdownMenu>
        <DropdownMenuTrigger
          className={cn(
            "hidden h-8 max-w-[min(100%,22rem)] shrink-0 items-center gap-1.5 truncate rounded-md border border-border bg-background px-2.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground sm:inline-flex",
          )}
          aria-label={`Session: ${dept}, ${personaLabel}, ${speedLabel}`}
        >
          <span className="truncate">
            {dept} · {personaLabel}
          </span>
          <span className="shrink-0 border-l border-border pl-1.5 font-semibold uppercase tracking-wide text-primary">
            {speedLabel}
          </span>
          <ChevronDown className="h-3 w-3 shrink-0 opacity-60" aria-hidden />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="z-[70] w-64">
          <DropdownMenuLabel className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Department
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup value={department} onValueChange={onDepartmentChange}>
            {DEPARTMENT_OPTIONS.map((option) => (
              <DropdownMenuRadioItem key={option.id} value={option.id} className="text-xs">
                {option.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Response style
          </DropdownMenuLabel>
          {CHAT_PERSONA_OPTIONS.map((option) => (
            <DropdownMenuItem
              key={option.key}
              disabled={personaDisabled}
              className={cn(
                "flex items-center justify-between gap-2 text-xs",
                persona === option.key && "bg-primary/10 text-primary",
              )}
              onClick={() => onPersonaChange(option.key)}
            >
              <span>{option.label}</span>
              {persona === option.key ? <Check className="h-3.5 w-3.5" /> : null}
            </DropdownMenuItem>
          ))}
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Speed
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={chatMode}
            onValueChange={(v) => onChatModeChange(v as ChatSpeed)}
          >
            <DropdownMenuRadioItem value="fast" className="text-xs">
              Fast — lighter reasoning
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="deep" className="text-xs">
              Agent — full tool surface
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Mobile — three chips (handoff 4*) */}
      <div className="flex min-w-0 items-center gap-1.5 overflow-x-auto sm:hidden">
        <DropdownMenu>
          <ChipTrigger aria-label={`Department: ${dept}`}>
            <span className="truncate">{dept === "All departments" ? "All" : dept}</span>
          </ChipTrigger>
          <DropdownMenuContent align="start" className="z-[70] w-56">
            <DropdownMenuRadioGroup value={department} onValueChange={onDepartmentChange}>
              {DEPARTMENT_OPTIONS.map((option) => (
                <DropdownMenuRadioItem key={option.id} value={option.id} className="text-xs">
                  {option.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>

        <button
          type="button"
          onClick={() => onChatModeChange(chatMode === "deep" ? "fast" : "deep")}
          className={cn(
            "h-8 shrink-0 rounded-full border px-2.5 text-[11px] font-bold uppercase tracking-wide",
            chatMode === "deep"
              ? "border-info/30 bg-info/10 text-info"
              : "border-primary/25 bg-primary/5 text-primary",
          )}
          title={
            chatMode === "deep"
              ? "Agent mode — full connector tool surface"
              : "Fast mode — lighter reasoning"
          }
          aria-label={`Speed: ${speedLabel}. Tap to switch.`}
        >
          {speedLabel}
        </button>

        <DropdownMenu>
          <ChipTrigger aria-label={`Response style: ${personaLabel}`} className="max-w-[9rem]">
            <span className="truncate">{personaLabel}</span>
          </ChipTrigger>
          <DropdownMenuContent align="end" className="z-[70] w-56">
            {CHAT_PERSONA_OPTIONS.map((option) => (
              <DropdownMenuItem
                key={option.key}
                disabled={personaDisabled}
                className={cn(
                  "text-xs",
                  persona === option.key && "bg-primary/10 text-primary",
                )}
                onClick={() => onPersonaChange(option.key)}
              >
                {option.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}
