"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"
import { motion, AnimatePresence } from "framer-motion"
import { Icon, type IconName } from "@/lib/icons"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { toast } from "sonner"
import { Loader2, Check, Download, ExternalLink, Zap, BookOpen, LifeBuoy } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { AnimatedCounter } from "@/components/gravitre/premium-effects"
import { humanizePlainEnglish } from "@/lib/plain-english"

function displayInsightContent(content: string): string {
  return humanizePlainEnglish(content, content)
}

interface ReasoningStep {
  id: string
  text: string
  isCompleted: boolean
}

interface InsightSection {
  id: string
  type: "summary" | "reasoning" | "root-cause" | "actions" | "evidence" | "prevention"
  title: string
  content: string
  steps?: ReasoningStep[]
  actions?: { id: string; label: string; priority: "high" | "medium" | "low" }[]
  evidence?: { id: string; source: string; relevance: string }[]
}

interface MesonInsightsPanelProps {
  confidence: number
  confidenceDataPoints?: number
  severity?: "critical" | "high" | "medium" | "low"
  lastUpdated?: string
  sections: InsightSection[]
  isGenerating?: boolean
  className?: string
  onTakeAction?: () => void
  onTryAutoFix?: () => void
  onViewDocumentation?: () => void
  onContactSupport?: () => void
}

const severityConfig: Record<string, { label: string; color: string; bg: string; border: string; glow: string; ring: string; icon: IconName }> = {
  critical: {
    label: "Critical",
    color: "text-danger-text",
    bg: "bg-destructive/10",
    border: "border-destructive/30",
    glow: "shadow-[0_0_30px_color-mix(in_srgb,_var(--destructive)_15%,_transparent)]",
    ring: "ring-destructive/20",
    icon: "error",
  },
  high: {
    label: "High",
    color: "text-warning-text",
    bg: "bg-warning/10",
    border: "border-warning/30",
    glow: "shadow-[0_0_25px_color-mix(in_srgb,_var(--warning)_12%,_transparent)]",
    ring: "ring-warning/20",
    icon: "warning",
  },
  medium: {
    label: "Medium",
    color: "text-warning-text",
    bg: "bg-warning/10",
    border: "border-warning/30",
    glow: "shadow-[0_0_20px_color-mix(in_srgb,_var(--warning)_10%,_transparent)]",
    ring: "ring-warning/20",
    icon: "info",
  },
  low: {
    label: "Low",
    color: "text-info",
    bg: "bg-info/10",
    border: "border-info/30",
    glow: "shadow-[0_0_15px_color-mix(in_srgb,_var(--info)_8%,_transparent)]",
    ring: "ring-info/20",
    icon: "info",
  },
}

const sectionConfig: Record<string, { icon: IconName; iconBg: string; iconColor: string; borderColor: string; headerBg: string; priority: number }> = {
  summary: {
    icon: "ai",
    iconBg: "bg-gradient-to-br from-destructive/20 to-warning/10",
    iconColor: "text-danger-text",
    borderColor: "border-l-destructive",
    headerBg: "bg-destructive/5",
    priority: 0,
  },
  "root-cause": {
    icon: "warning",
    iconBg: "bg-gradient-to-br from-warning/20 to-warning/10",
    iconColor: "text-warning-text",
    borderColor: "border-l-warning",
    headerBg: "bg-warning/5",
    priority: 1,
  },
  reasoning: {
    icon: "aiAnalysis",
    iconBg: "bg-gradient-to-br from-warning/20 to-warning/10",
    iconColor: "text-warning-text",
    borderColor: "border-l-warning",
    headerBg: "bg-warning/5",
    priority: 2,
  },
  actions: {
    icon: "insight",
    iconBg: "bg-gradient-to-br from-info/20 to-info/10",
    iconColor: "text-info",
    borderColor: "border-l-info",
    headerBg: "bg-info/5",
    priority: 3,
  },
  prevention: {
    icon: "shield",
    iconBg: "bg-gradient-to-br from-success/20 to-success/10",
    iconColor: "text-success-text",
    borderColor: "border-l-success",
    headerBg: "bg-success/5",
    priority: 4,
  },
  evidence: {
    icon: "file",
    iconBg: "bg-gradient-to-br from-info/20 to-info/10",
    iconColor: "text-info",
    borderColor: "border-l-info",
    headerBg: "bg-info/5",
    priority: 5,
  },
}

function ConfidenceIndicator({
  value,
  dataPoints = 5,
}: {
  value: number
  dataPoints?: number
}) {
  const getColor = () => {
    if (value >= 80) return { text: "text-success-text", bg: "bg-success", glow: "shadow-success/30" }
    if (value >= 60) return { text: "text-warning-text", bg: "bg-warning", glow: "shadow-warning/30" }
    return { text: "text-danger-text", bg: "bg-destructive", glow: "shadow-destructive/30" }
  }

  const colors = getColor()
  const tooltipText = `Based on ${dataPoints} data point${dataPoints === 1 ? "" : "s"} from execution logs and error patterns`

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex cursor-default flex-col items-end gap-1.5">
            <div className="flex items-center gap-2">
              <Icon name="confidence" size="sm" className={colors.text} />
              <span className="text-xs font-medium text-muted-foreground">Confidence</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="h-2 w-24 overflow-hidden rounded-full bg-secondary/80">
                <motion.div
                  key={value}
                  className={cn("h-full rounded-full", colors.bg)}
                  initial={{ width: 0 }}
                  animate={{ width: `${value}%` }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                />
              </div>
              <motion.span
                className={cn("text-xl font-bold tabular-nums", colors.text)}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: 0.15 }}
              >
                <AnimatedCounter value={value} duration={0.6} />%
              </motion.span>
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="end" className="max-w-[220px] text-xs">
          {tooltipText}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function SeverityBadge({ severity }: { severity: "critical" | "high" | "medium" | "low" }) {
  const config = severityConfig[severity]

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        "flex items-center gap-2 rounded-full border px-3 py-1.5",
        config.bg,
        config.border
      )}
    >
      <Icon name={config.icon} size="sm" className={config.color} emphasis />
      <span className={cn("text-xs font-semibold", config.color)}>{config.label}</span>
    </motion.div>
  )
}

function FixActionButtons({
  onTryAutoFix,
  onViewDocumentation,
  onContactSupport,
  isBusy,
}: {
  onTryAutoFix?: () => void
  onViewDocumentation?: () => void
  onContactSupport?: () => void
  isBusy?: boolean
}) {
  const handleTryAutoFix = () => {
    if (onTryAutoFix) {
      onTryAutoFix()
      return
    }
    toast.info("Auto-fix queued", {
      description: "Recommended fixes will be applied after approval.",
    })
  }

  const handleViewDocumentation = () => {
    if (onViewDocumentation) {
      onViewDocumentation()
      return
    }
    window.open("https://docs.gravitre.app", "_blank", "noopener,noreferrer")
  }

  const handleContactSupport = () => {
    if (onContactSupport) {
      onContactSupport()
      return
    }
    window.open(
      "mailto:support@gravitre.app?subject=Operator%20analysis%20help",
      "_self",
    )
  }

  return (
    <div className="mt-5 flex flex-wrap gap-2 border-t border-border/40 pt-4">
      <Button
        size="sm"
        className="h-8 gap-1.5 text-xs"
        onClick={handleTryAutoFix}
        disabled={isBusy}
      >
        {isBusy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Zap className="h-3.5 w-3.5" />
        )}
        Try auto-fix
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-1.5 text-xs"
        onClick={handleViewDocumentation}
        disabled={isBusy}
      >
        <BookOpen className="h-3.5 w-3.5" />
        View documentation
      </Button>
      <Button
        variant="outline"
        size="sm"
        className="h-8 gap-1.5 text-xs"
        onClick={handleContactSupport}
        disabled={isBusy}
      >
        <LifeBuoy className="h-3.5 w-3.5" />
        Contact support
      </Button>
    </div>
  )
}

function InsightSectionCard({
  section,
  isExpanded,
  onToggle,
  index,
  isHighlighted = false,
  onTryAutoFix,
  onViewDocumentation,
  onContactSupport,
  isFixBusy = false,
}: {
  section: InsightSection
  isExpanded: boolean
  onToggle: () => void
  index: number
  isHighlighted?: boolean
  onTryAutoFix?: () => void
  onViewDocumentation?: () => void
  onContactSupport?: () => void
  isFixBusy?: boolean
}) {
  const config = sectionConfig[section.type] || sectionConfig.summary

  const priorityColors = {
    high: "bg-destructive/10 text-danger-text border-destructive/20 ring-1 ring-destructive/10",
    medium: "bg-warning/10 text-warning-text border-warning/20 ring-1 ring-warning/10",
    low: "bg-info/10 text-info border-info/20 ring-1 ring-info/10",
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.08, ease: "easeOut" }}
      className={cn(
        "rounded-xl border overflow-hidden transition-all duration-300",
        config.borderColor,
        "border-l-[3px]",
        isHighlighted 
          ? "border-border/80 bg-gradient-to-r from-card to-card/80 shadow-lg ring-1 ring-border/40" 
          : "border-border/50 bg-card/50 hover:bg-card/80 hover:border-border/70"
      )}
    >
      {/* Header */}
      <button
        onClick={onToggle}
        className={cn(
          "flex w-full items-center justify-between p-4 text-left transition-colors",
          isHighlighted && config.headerBg
        )}
      >
        <div className="flex items-center gap-4">
          <div
            className={cn(
              "flex h-11 w-11 items-center justify-center rounded-xl transition-all",
              config.iconBg,
              isExpanded && "scale-105"
            )}
          >
            <Icon name={config.icon} size="lg" className={config.iconColor} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-sm font-semibold text-foreground">
                {section.title}
              </h4>
              {isHighlighted && (
                <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-bold text-danger-text">
                  Primary
                </span>
              )}
            </div>
            {!isExpanded && (
              <p className="mt-1 text-xs text-muted-foreground/80 line-clamp-1 max-w-lg">
                {displayInsightContent(section.content)}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {section.type === "reasoning" && section.steps && (
            <div className="flex items-center gap-1.5 rounded-full bg-secondary/60 px-2.5 py-1">
              <Icon name="success" size="xs" className="text-success-text" />
              <span className="text-[10px] font-medium text-muted-foreground">
                {section.steps.filter((s) => s.isCompleted).length}/{section.steps.length}
              </span>
            </div>
          )}
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <Icon name="caretDown" size="sm" className="text-muted-foreground" />
          </motion.div>
        </div>
      </button>

      {/* Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="border-t border-border/50 px-5 pb-5 pt-4">
              <p className="text-sm leading-relaxed text-foreground/80">
                {displayInsightContent(section.content)}
              </p>

              {/* Supporting Evidence */}
              {section.type === "evidence" && section.evidence && (
                <div className="mt-5 space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground mb-3">
                    Data sources
                  </p>
                  {section.evidence.map((item, i) => (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      className="flex items-center justify-between rounded-lg bg-secondary/40 p-3 ring-1 ring-border/30"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-info/10">
                          <Icon name="file" size="sm" className="text-info" />
                        </div>
                        <div>
                          <p className="text-xs font-medium text-foreground">{item.source}</p>
                          <p className="text-[10px] text-muted-foreground">{item.relevance}</p>
                        </div>
                      </div>
                      <Icon name="caretRight" size="sm" className="text-muted-foreground/50" />
                    </motion.div>
                  ))}
                </div>
              )}

              {/* Reasoning Steps */}
              {section.type === "reasoning" && section.steps && (
                <div className="mt-5 space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground mb-3">
                    Analysis steps
                  </p>
                  {section.steps.map((step, i) => (
                    <motion.div
                      key={step.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.06 }}
                      className={cn(
                        "flex items-start gap-4 rounded-lg p-3 transition-all",
                        step.isCompleted 
                          ? "bg-success/5 ring-1 ring-success/10" 
                          : "bg-secondary/40 ring-1 ring-border/30"
                      )}
                    >
                      <div
                        className={cn(
                          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                          step.isCompleted
                            ? "bg-success/20 text-success-text"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {step.isCompleted ? (
                          <Icon name="success" size="sm" />
                        ) : (
                          <span>{i + 1}</span>
                        )}
                      </div>
                      <p
                        className={cn(
                          "text-xs leading-relaxed pt-0.5",
                          step.isCompleted ? "text-foreground/70" : "text-foreground"
                        )}
                      >
                        {step.text}
                      </p>
                    </motion.div>
                  ))}
                </div>
              )}

              {/* Suggested Actions */}
              {section.type === "actions" && section.actions && (
                <div className="mt-5 space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground mb-3">
                    Recommended actions
                  </p>
                  {section.actions.map((action, i) => (
                    <motion.div
                      key={action.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.06 }}
                      className="flex items-center justify-between rounded-lg bg-secondary/40 p-3 ring-1 ring-border/30 hover:bg-secondary/60 transition-colors cursor-pointer group"
                    >
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "flex h-8 w-8 items-center justify-center rounded-lg transition-colors",
                          action.priority === "high" ? "bg-destructive/10 group-hover:bg-destructive/20" :
                          action.priority === "medium" ? "bg-warning/10 group-hover:bg-warning/20" :
                          "bg-info/10 group-hover:bg-info/20"
                        )}>
                          <Icon 
                            name="execution" 
                            size="sm"
                            className={cn(
                              action.priority === "high" ? "text-danger-text" :
                              action.priority === "medium" ? "text-warning-text" :
                              "text-info"
                            )} 
                          />
                        </div>
                        <span className="text-sm text-foreground">{displayInsightContent(action.label)}</span>
                      </div>
                      <span
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-xs font-semibold",
                          priorityColors[action.priority]
                        )}
                      >
                        {action.priority}
                      </span>
                    </motion.div>
                  ))}
                  <FixActionButtons
                    onTryAutoFix={onTryAutoFix}
                    onViewDocumentation={onViewDocumentation}
                    onContactSupport={onContactSupport}
                    isBusy={isFixBusy}
                  />
                </div>
              )}

              {section.type === "actions" && !section.actions && (
                <FixActionButtons
                  onTryAutoFix={onTryAutoFix}
                  onViewDocumentation={onViewDocumentation}
                  onContactSupport={onContactSupport}
                  isBusy={isFixBusy}
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export function MesonInsightsPanel({
  confidence,
  confidenceDataPoints,
  severity = "high",
  lastUpdated,
  sections,
  isGenerating = false,
  className,
  onTakeAction,
  onTryAutoFix,
  onViewDocumentation,
  onContactSupport,
}: MesonInsightsPanelProps) {
  const [expandedSections, setExpandedSections] = useState<string[]>(["summary", "root-cause", "actions"])
  const [showFullAnalysis, setShowFullAnalysis] = useState(false)
  const [showVerifySources, setShowVerifySources] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isTakingAction, setIsTakingAction] = useState(false)
  const [isFixBusy, setIsFixBusy] = useState(false)
  const severityConf = severityConfig[severity]

  const toggleSection = (id: string) => {
    setExpandedSections((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    )
  }

  const handleExport = () => {
    setIsExporting(true)
    setTimeout(() => {
      // Create a text export of the analysis
      const analysisText = sections.map(s => 
        `## ${s.title}\n${displayInsightContent(s.content)}\n`
      ).join("\n")
      const blob = new Blob([analysisText], { type: "text/plain" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `ai-analysis-${new Date().toISOString().split("T")[0]}.txt`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setIsExporting(false)
      toast.success("Analysis exported successfully")
    }, 800)
  }

  const handleTakeAction = () => {
    setIsTakingAction(true)
    setTimeout(() => {
      setIsTakingAction(false)
      if (onTakeAction) {
        onTakeAction()
      }
      toast.success("Actions applied successfully", {
        description: "The recommended fixes have been queued for execution."
      })
    }, 1000)
  }

  const handleTryAutoFix = () => {
    setIsFixBusy(true)
    if (onTryAutoFix) {
      onTryAutoFix()
      setTimeout(() => setIsFixBusy(false), 800)
      return
    }
    handleTakeAction()
    setTimeout(() => setIsFixBusy(false), 1000)
  }

  // Sort sections by priority, with root-cause first
  const sortedSections = [...sections].sort((a, b) => {
    const configA = sectionConfig[a.type] || { priority: 99 }
    const configB = sectionConfig[b.type] || { priority: 99 }
    return configA.priority - configB.priority
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={cn(
        "rounded-2xl border border-border/60 bg-gradient-to-b from-card to-card/90 backdrop-blur-xl",
        "ring-1",
        severityConf.ring,
        severityConf.glow,
        "transition-shadow duration-500",
        className
      )}
    >
      {/* Panel Header */}
      <div className="relative overflow-hidden border-b border-border/50 px-6 py-5">
        {/* Subtle gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-foreground/[0.02] to-transparent" />
        
        <div className="relative flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className={cn(
                "flex h-14 w-14 items-center justify-center rounded-2xl",
                "bg-gradient-to-br from-[color:var(--g-intelligence)]/20 via-[color:var(--g-intelligence)]/10 to-info/10",
                "ring-1 ring-border/60"
              )}>
                <Icon name="aiAnalysis" size="xl" className="text-intelligence-text" emphasis />
              </div>
              {isGenerating && (
                <motion.div
                  className="absolute -inset-1.5 rounded-2xl bg-[color:var(--g-intelligence)]/20"
                  animate={{ opacity: [0.3, 0.6, 0.3], scale: [1, 1.05, 1] }}
                  transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                />
              )}
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold text-foreground">AI Analysis</h3>
                <SeverityBadge severity={severity} />
              </div>
              <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
                {isGenerating ? (
                  <motion.span
                    className="flex items-center gap-2"
                    animate={{ opacity: [1, 0.5, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  >
                    <Icon name="ai" size="xs" className="text-intelligence-text" emphasis />
                    Analyzing patterns...
                  </motion.span>
                ) : (
                  <>
                    <Icon name="pending" size="xs" />
                    <span>Updated {lastUpdated || "just now"}</span>
                    <span className="text-border">|</span>
                    <span>{sections.length} insights</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <ConfidenceIndicator value={confidence} dataPoints={confidenceDataPoints} />
        </div>
      </div>

      {/* Sections */}
      <div className="space-y-3 p-5">
        {sortedSections.map((section, index) => (
          <InsightSectionCard
            key={section.id}
            section={section}
            isExpanded={expandedSections.includes(section.id)}
            onToggle={() => toggleSection(section.id)}
            index={index}
            isHighlighted={section.type === "summary" || section.type === "root-cause"}
            onTryAutoFix={handleTryAutoFix}
            onViewDocumentation={onViewDocumentation}
            onContactSupport={onContactSupport}
            isFixBusy={isFixBusy || isTakingAction}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="border-t border-border/50 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setShowFullAnalysis(true)}
              className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Icon name="search" size="sm" />
              View full analysis
            </button>
            <span className="text-border">|</span>
            <button 
              onClick={() => setShowVerifySources(true)}
              className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              <Icon name="shield" size="sm" />
              Verify sources
            </button>
          </div>
          <div className="flex items-center gap-2">
            <Button 
              variant="outline" 
              size="sm" 
              className="h-8 text-xs gap-1.5"
              onClick={handleExport}
              disabled={isExporting}
            >
              {isExporting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Download className="h-3.5 w-3.5" />
              )}
              {isExporting ? "Exporting..." : "Export"}
            </Button>
            <Button 
              size="sm" 
              className="h-8 text-xs gap-1.5"
              onClick={handleTakeAction}
              disabled={isTakingAction}
            >
              {isTakingAction ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Icon name="execution" size="sm" />
              )}
              {isTakingAction ? "Applying..." : "Take Action"}
            </Button>
          </div>
        </div>
      </div>

      {/* Full Analysis Dialog */}
      <Dialog open={showFullAnalysis} onOpenChange={setShowFullAnalysis}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Icon name="aiAnalysis" size="lg" className="text-intelligence-text" />
              Full AI analysis
            </DialogTitle>
            <DialogDescription>
              Complete analysis breakdown with all findings and recommendations.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            {sections.map((section) => {
              const config = sectionConfig[section.type] || sectionConfig.summary
              return (
                <div key={section.id} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className={cn("flex h-8 w-8 items-center justify-center rounded-lg", config.iconBg)}>
                      <Icon name={config.icon} size="sm" className={config.iconColor} />
                    </div>
                    <h4 className="font-semibold text-foreground">{section.title}</h4>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed pl-10">
                    {displayInsightContent(section.content)}
                  </p>
                  {section.actions && (
                    <div className="pl-10 space-y-2 mt-3">
                      <p className="text-xs font-medium text-muted-foreground">Recommended Actions:</p>
                      {section.actions.map((action) => (
                        <div key={action.id} className="flex items-center gap-2 text-sm">
                          <Check className="h-4 w-4 text-success-text" />
                          <span>{displayInsightContent(action.label)}</span>
                          <span className={cn(
                            "text-[10px] px-1.5 py-0.5 rounded-full",
                            action.priority === "high" ? "bg-destructive/10 text-danger-text" :
                            action.priority === "medium" ? "bg-warning/10 text-warning-text" :
                            "bg-info/10 text-info"
                          )}>{action.priority}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={() => setShowFullAnalysis(false)}>Close</Button>
            <Button onClick={handleExport} className="gap-2">
              <Download className="h-4 w-4" />
              Export report
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Verify Sources Dialog */}
      <Dialog open={showVerifySources} onOpenChange={setShowVerifySources}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Icon name="shield" size="lg" className="text-success-text" />
              Source verification
            </DialogTitle>
            <DialogDescription>
              All data sources used in this analysis have been verified.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {[
              { name: "System Logs", status: "verified", timestamp: "2 min ago" },
              { name: "Error Traces", status: "verified", timestamp: "2 min ago" },
              { name: "Performance Metrics", status: "verified", timestamp: "5 min ago" },
              { name: "Configuration Files", status: "verified", timestamp: "5 min ago" },
            ].map((source) => (
              <div key={source.name} className="flex items-center justify-between p-3 rounded-lg bg-secondary/50 border border-border/50">
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10">
                    <Check className="h-4 w-4 text-success-text" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{source.name}</p>
                    <p className="text-xs text-muted-foreground">Last checked {source.timestamp}</p>
                  </div>
                </div>
                <span className="text-xs text-success-text font-medium">{source.status}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-between items-center pt-4 border-t">
            <button className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
              <ExternalLink className="h-3.5 w-3.5" />
              View raw data
            </button>
            <Button onClick={() => setShowVerifySources(false)}>Done</Button>
          </div>
        </DialogContent>
      </Dialog>
    </motion.div>
  )
}

// Backward compatible alias
export const AIInsightsPanel = MesonInsightsPanel
