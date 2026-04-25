"use client"

import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  ChevronDown, 
  Sparkles, 
  Zap, 
  Brain, 
  Gauge, 
  Clock,
  Check,
  Settings2,
  RotateCcw,
  Info,
  ChevronRight
} from "lucide-react"
import { cn } from "@/lib/utils"

// Model definitions
export interface Model {
  id: string
  name: string
  shortName: string
  category: "fast" | "balanced" | "reasoning" | "long-context" | "low-cost"
  description: string
  badges: Array<"fast" | "best-reasoning" | "low-cost" | "long-context" | "recommended">
  contextWindow?: string
  provider?: string
}

export const models: Model[] = [
  {
    id: "auto",
    name: "Auto-select",
    shortName: "Auto",
    category: "balanced",
    description: "Automatically picks the best model for the task",
    badges: ["recommended"],
  },
  {
    id: "fast",
    name: "Fast Model",
    shortName: "Fast",
    category: "fast",
    description: "Optimized for speed and simple tasks",
    badges: ["fast"],
    contextWindow: "16K",
  },
  {
    id: "balanced",
    name: "Balanced Model",
    shortName: "Balanced",
    category: "balanced",
    description: "Good balance of speed and quality",
    badges: [],
    contextWindow: "32K",
  },
  {
    id: "reasoning",
    name: "Reasoning Model",
    shortName: "Reasoning",
    category: "reasoning",
    description: "Best for complex analysis and multi-step problems",
    badges: ["best-reasoning"],
    contextWindow: "128K",
  },
  {
    id: "long-context",
    name: "Long Context Model",
    shortName: "Long Context",
    category: "long-context",
    description: "Handles very large documents and conversations",
    badges: ["long-context"],
    contextWindow: "200K",
  },
  {
    id: "low-cost",
    name: "Low Cost Model",
    shortName: "Economy",
    category: "low-cost",
    description: "Cost-effective for high-volume operations",
    badges: ["low-cost"],
    contextWindow: "8K",
  },
]

const categoryIcons = {
  fast: Zap,
  balanced: Gauge,
  reasoning: Brain,
  "long-context": Clock,
  "low-cost": Sparkles,
}

const badgeStyles = {
  fast: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  "best-reasoning": "bg-violet-500/10 text-violet-500 border-violet-500/20",
  "low-cost": "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  "long-context": "bg-blue-500/10 text-blue-500 border-blue-500/20",
  recommended: "bg-info/10 text-info border-info/20",
}

const badgeLabels = {
  fast: "Fast",
  "best-reasoning": "Best for reasoning",
  "low-cost": "Low cost",
  "long-context": "Long context",
  recommended: "Recommended",
}

// Inheritance indicator
export type InheritanceSource = "workspace" | "agent" | "override" | null

interface ModelSelectorProps {
  value: string
  onChange: (modelId: string) => void
  inheritedFrom?: InheritanceSource
  onResetToDefault?: () => void
  showAdvanced?: boolean
  size?: "sm" | "md"
  disabled?: boolean
  className?: string
}

export function ModelSelector({
  value,
  onChange,
  inheritedFrom,
  onResetToDefault,
  showAdvanced = false,
  size = "md",
  disabled = false,
  className,
}: ModelSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [showAdvancedPanel, setShowAdvancedPanel] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const selectedModel = models.find((m) => m.id === value) || models[0]
  const Icon = categoryIcons[selectedModel.category]

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
        setShowAdvancedPanel(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const isOverridden = inheritedFrom === "override"
  const isInherited = inheritedFrom === "workspace" || inheritedFrom === "agent"

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
        className={cn(
          "group flex items-center gap-2 rounded-lg border bg-card transition-all duration-200",
          "hover:border-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-ring/50",
          isOpen && "border-info/50 ring-2 ring-info/20",
          isOverridden && "border-info/30",
          disabled && "opacity-50 cursor-not-allowed",
          size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-3 py-2 text-sm"
        )}
      >
        {/* Model icon with glow effect */}
        <div className={cn(
          "flex items-center justify-center rounded-md transition-all",
          size === "sm" ? "h-5 w-5" : "h-6 w-6",
          value === "auto" 
            ? "bg-gradient-to-br from-info/20 to-violet-500/20 text-info" 
            : "bg-secondary text-muted-foreground group-hover:text-foreground"
        )}>
          {value === "auto" ? (
            <Sparkles className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
          ) : (
            <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
          )}
        </div>

        {/* Model name */}
        <span className="font-medium text-foreground">
          {selectedModel.shortName}
        </span>

        {/* Inheritance indicator */}
        {isInherited && (
          <span className="text-[10px] text-muted-foreground">
            ({inheritedFrom})
          </span>
        )}

        {/* Override indicator */}
        {isOverridden && (
          <span className="flex h-1.5 w-1.5 rounded-full bg-info" />
        )}

        <ChevronDown className={cn(
          "text-muted-foreground transition-transform",
          size === "sm" ? "h-3 w-3" : "h-4 w-4",
          isOpen && "rotate-180"
        )} />
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.15 }}
            className={cn(
              "absolute z-50 mt-2 w-72 rounded-xl border border-border bg-card shadow-xl shadow-black/20",
              "overflow-hidden"
            )}
          >
            {/* Header with reset option */}
            {(isOverridden && onResetToDefault) && (
              <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-secondary/30">
                <span className="text-xs text-muted-foreground">Model overridden</span>
                <button
                  onClick={() => {
                    onResetToDefault()
                    setIsOpen(false)
                  }}
                  className="flex items-center gap-1 text-xs text-info hover:text-info/80 transition-colors"
                >
                  <RotateCcw className="h-3 w-3" />
                  Reset to default
                </button>
              </div>
            )}

            {/* Model list */}
            <div className="p-1.5 max-h-[320px] overflow-y-auto">
              {models.map((model) => {
                const ModelIcon = model.id === "auto" ? Sparkles : categoryIcons[model.category]
                const isSelected = model.id === value

                return (
                  <button
                    key={model.id}
                    onClick={() => {
                      onChange(model.id)
                      setIsOpen(false)
                    }}
                    className={cn(
                      "group w-full flex items-start gap-3 rounded-lg p-2.5 text-left transition-all",
                      "hover:bg-secondary/70",
                      isSelected && "bg-info/10"
                    )}
                  >
                    {/* Icon */}
                    <div className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-all",
                      model.id === "auto"
                        ? "bg-gradient-to-br from-info/20 to-violet-500/20 text-info"
                        : isSelected
                          ? "bg-info/20 text-info"
                          : "bg-secondary text-muted-foreground group-hover:text-foreground"
                    )}>
                      <ModelIcon className="h-4 w-4" />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "text-sm font-medium",
                          isSelected ? "text-info" : "text-foreground"
                        )}>
                          {model.name}
                        </span>
                        {isSelected && (
                          <Check className="h-3.5 w-3.5 text-info" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                        {model.description}
                      </p>
                      {/* Badges */}
                      {model.badges.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {model.badges.map((badge) => (
                            <span
                              key={badge}
                              className={cn(
                                "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border",
                                badgeStyles[badge]
                              )}
                            >
                              {badgeLabels[badge]}
                            </span>
                          ))}
                          {model.contextWindow && (
                            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-secondary text-muted-foreground">
                              {model.contextWindow}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Advanced settings toggle */}
            {showAdvanced && (
              <div className="border-t border-border">
                <button
                  onClick={() => setShowAdvancedPanel(!showAdvancedPanel)}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <Settings2 className="h-3.5 w-3.5" />
                    Advanced settings
                  </span>
                  <ChevronRight className={cn(
                    "h-3.5 w-3.5 transition-transform",
                    showAdvancedPanel && "rotate-90"
                  )} />
                </button>

                <AnimatePresence>
                  {showAdvancedPanel && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="px-3 pb-3 space-y-3">
                        {/* Temperature */}
                        <div>
                          <label className="text-[10px] font-medium text-muted-foreground uppercase tracking-wide">
                            Temperature
                          </label>
                          <input
                            type="range"
                            min="0"
                            max="2"
                            step="0.1"
                            defaultValue="0.7"
                            className="w-full h-1.5 mt-1.5 rounded-full appearance-none bg-secondary cursor-pointer"
                          />
                          <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                            <span>Precise</span>
                            <span>Creative</span>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// Compact inline model indicator (for read-only display)
export function ModelIndicator({
  modelId,
  inheritedFrom,
  size = "sm",
  className,
}: {
  modelId: string
  inheritedFrom?: InheritanceSource
  size?: "sm" | "xs"
  className?: string
}) {
  const model = models.find((m) => m.id === modelId) || models[0]
  const Icon = modelId === "auto" ? Sparkles : categoryIcons[model.category]

  return (
    <div className={cn(
      "inline-flex items-center gap-1.5 rounded-md bg-secondary/50 border border-border",
      size === "xs" ? "px-1.5 py-0.5 text-[10px]" : "px-2 py-1 text-xs",
      className
    )}>
      <Icon className={size === "xs" ? "h-2.5 w-2.5" : "h-3 w-3"} />
      <span className="font-medium text-foreground">{model.shortName}</span>
      {inheritedFrom && inheritedFrom !== "override" && (
        <span className="text-muted-foreground">({inheritedFrom})</span>
      )}
    </div>
  )
}

// Inheritance chain visualization
export function ModelInheritanceChain({
  workspaceModel = "auto",
  agentModel,
  taskModel,
  className,
}: {
  workspaceModel?: string
  agentModel?: string
  taskModel?: string
  className?: string
}) {
  const levels = [
    { label: "Workspace", model: workspaceModel, active: !agentModel && !taskModel },
    { label: "Agent", model: agentModel, active: agentModel && !taskModel },
    { label: "Task", model: taskModel, active: Boolean(taskModel) },
  ].filter((l) => l.model)

  return (
    <div className={cn("flex items-center gap-1 text-xs", className)}>
      {levels.map((level, i) => {
        const model = models.find((m) => m.id === level.model)
        return (
          <div key={level.label} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="h-3 w-3 text-muted-foreground" />}
            <span className={cn(
              "px-1.5 py-0.5 rounded",
              level.active 
                ? "bg-info/10 text-info font-medium" 
                : "text-muted-foreground"
            )}>
              {level.label}: {model?.shortName || "Default"}
            </span>
          </div>
        )
      })}
    </div>
  )
}
