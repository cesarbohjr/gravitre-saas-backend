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
import { Loader2, Check, Download, ExternalLink } from "lucide-react"

interface ReasoningStep {
  id: string
  text: string
  isCompleted: boolean
}

interface InsightSection {
  id: string
  type: "summary" | "reasoning" | "root-cause" | "actions" | "evidence"
  title: string
  content: string
  steps?: ReasoningStep[]
  actions?: { id: string; label: string; priority: "high" | "medium" | "low" }[]
  evidence?: { id: string; source: string; relevance: string }[]
}

interface MesonInsightsPanelProps {
  confidence: number
  severity?: "critical" | "high" | "medium" | "low"
  lastUpdated?: string
  sections: InsightSection[]
  isGenerating?: boolean
  className?: string
  onTakeAction?: () => void
}

const severityConfig: Record<string, { label: string; color: string; bg: string; border: string; glow: string; ring: string; icon: IconName }> = {
  critical: {
    label: "Critical",
    color: "text-red-400",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
    glow: "shadow-[0_0_30px_rgba(239,68,68,0.15)]",
    ring: "ring-red-500/20",
    icon: "error",
  },
  high: {
    label: "High",
    color: "text-orange-400",
    bg: "bg-orange-500/10",
    border: "border-orange-500/30",
    glow: "shadow-[0_0_25px_rgba(249,115,22,0.12)]",
    ring: "ring-orange-500/20",
    icon: "warning",
  },
  medium: {
    label: "Medium",
    color: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
    glow: "shadow-[0_0_20px_rgba(245,158,11,0.1)]",
    ring: "ring-amber-500/20",
    icon: "info",
  },
  low: {
    label: "Low",
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
    glow: "shadow-[0_0_15px_rgba(59,130,246,0.08)]",
    ring: "ring-blue-500/20",
    icon: "info",
  },
}

const sectionConfig: Record<string, { icon: IconName; iconBg: string; iconColor: string; borderColor: string; headerBg: string; priority: number }> = {
  "root-cause": {
    icon: "warning",
    iconBg: "bg-gradient-to-br from-red-500/20 to-orange-500/10",
    iconColor: "text-red-400",
    borderColor: "border-l-red-500",
    headerBg: "bg-red-500/5",
    priority: 1,
  },
  evidence: {
    icon: "file",
    iconBg: "bg-gradient-to-br from-blue-500/20 to-cyan-500/10",
    iconColor: "text-blue-400",
    borderColor: "border-l-blue-500",
    headerBg: "bg-blue-500/5",
    priority: 2,
  },
  reasoning: {
    icon: "aiAnalysis",
    iconBg: "bg-gradient-to-br from-purple-500/20 to-pink-500/10",
    iconColor: "text-purple-400",
    borderColor: "border-l-purple-500",
    headerBg: "bg-purple-500/5",
    priority: 3,
  },
  actions: {
    icon: "insight",
    iconBg: "bg-gradient-to-br from-emerald-500/20 to-teal-500/10",
    iconColor: "text-emerald-400",
    borderColor: "border-l-emerald-500",
    headerBg: "bg-emerald-500/5",
    priority: 4,
  },
  summary: {
    icon: "ai",
    iconBg: "bg-gradient-to-br from-blue-500/20 to-indigo-500/10",
    iconColor: "text-blue-400",
    borderColor: "border-l-blue-500",
    headerBg: "bg-blue-500/5",
    priority: 0,
  },
}

function ConfidenceIndicator({ value }: { value: number }) {
  const getColor = () => {
    if (value >= 85) return { text: "text-emerald-400", bg: "bg-emerald-500", glow: "shadow-emerald-500/30" }
    if (value >= 70) return { text: "text-blue-400", bg: "bg-blue-500", glow: "shadow-blue-500/30" }
    if (value >= 50) return { text: "text-amber-400", bg: "bg-amber-500", glow: "shadow-amber-500/30" }
    return { text: "text-red-400", bg: "bg-red-500", glow: "shadow-red-500/30" }
  }

  const colors = getColor()

  return (
    <div className="flex flex-col items-end gap-1.5">
      <div className="flex items-center gap-2">
        <Icon name="confidence" size="sm" className={colors.text} />
        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Confidence</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="h-2 w-24 rounded-full bg-secondary/80 overflow-hidden">
          <motion.div
            className={cn("h-full rounded-full", colors.bg)}
            initial={{ width: 0 }}
            animate={{ width: `${value}%` }}
            transition={{ duration: 1, ease: "easeOut", delay: 0.2 }}
          />
        </div>
        <motion.span 
          className={cn("text-xl font-bold tabular-nums", colors.text)}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.3, delay: 0.5 }}
        >
          {value}%
        </motion.span>
      </div>
    </div>
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

function InsightSectionCard({
  section,
  isExpanded,
  onToggle,
  index,
  isHighlighted = false,
}: {
  section: InsightSection
  isExpanded: boolean
  onToggle: () => void
  index: number
  isHighlighted?: boolean
}) {
  const config = sectionConfig[section.type] || sectionConfig.summary

  const priorityColors = {
    high: "bg-red-500/10 text-red-400 border-red-500/20 ring-1 ring-red-500/10",
    medium: "bg-amber-500/10 text-amber-400 border-amber-500/20 ring-1 ring-amber-500/10",
    low: "bg-blue-500/10 text-blue-400 border-blue-500/20 ring-1 ring-blue-500/10",
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
          ? "border-border/80 bg-gradient-to-r from-card to-card/80 shadow-lg ring-1 ring-white/5" 
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
                <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-red-400">
                  Primary
                </span>
              )}
            </div>
            {!isExpanded && (
              <p className="mt-1 text-xs text-muted-foreground/80 line-clamp-1 max-w-lg">
                {section.content}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {section.type === "reasoning" && section.steps && (
            <div className="flex items-center gap-1.5 rounded-full bg-secondary/60 px-2.5 py-1">
              <Icon name="success" size="xs" className="text-emerald-400" />
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
                {section.content}
              </p>

              {/* Supporting Evidence */}
              {section.type === "evidence" && section.evidence && (
                <div className="mt-5 space-y-2">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    Data Sources
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
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
                          <Icon name="file" size="sm" className="text-blue-400" />
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
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    Analysis Steps
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
                          ? "bg-emerald-500/5 ring-1 ring-emerald-500/10" 
                          : "bg-secondary/40 ring-1 ring-border/30"
                      )}
                    >
                      <div
                        className={cn(
                          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium",
                          step.isCompleted
                            ? "bg-emerald-500/20 text-emerald-400"
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
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                    Recommended Actions
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
                          action.priority === "high" ? "bg-red-500/10 group-hover:bg-red-500/20" :
                          action.priority === "medium" ? "bg-amber-500/10 group-hover:bg-amber-500/20" :
                          "bg-blue-500/10 group-hover:bg-blue-500/20"
                        )}>
                          <Icon 
                            name="execution" 
                            size="sm"
                            className={cn(
                              action.priority === "high" ? "text-red-400" :
                              action.priority === "medium" ? "text-amber-400" :
                              "text-blue-400"
                            )} 
                          />
                        </div>
                        <span className="text-sm text-foreground">{action.label}</span>
                      </div>
                      <span
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide",
                          priorityColors[action.priority]
                        )}
                      >
                        {action.priority}
                      </span>
                    </motion.div>
                  ))}
                </div>
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
  severity = "high",
  lastUpdated,
  sections,
  isGenerating = false,
  className,
  onTakeAction,
}: MesonInsightsPanelProps) {
  const [expandedSections, setExpandedSections] = useState<string[]>(["root-cause", "summary"])
  const [showFullAnalysis, setShowFullAnalysis] = useState(false)
  const [showVerifySources, setShowVerifySources] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [isTakingAction, setIsTakingAction] = useState(false)
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
        `## ${s.title}\n${s.content}\n`
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
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.02] to-transparent" />
        
        <div className="relative flex items-start justify-between">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className={cn(
                "flex h-14 w-14 items-center justify-center rounded-2xl",
                "bg-gradient-to-br from-blue-500/20 via-purple-500/10 to-pink-500/10",
                "ring-1 ring-white/10"
              )}>
                <Icon name="aiAnalysis" size="xl" className="text-blue-400" emphasis />
              </div>
              {isGenerating && (
                <motion.div
                  className="absolute -inset-1.5 rounded-2xl bg-blue-500/20"
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
                    <Icon name="ai" size="xs" className="text-blue-400" emphasis />
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
          <ConfidenceIndicator value={confidence} />
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
            isHighlighted={section.type === "root-cause"}
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
              className="h-8 text-xs gap-1.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400"
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
              <Icon name="aiAnalysis" size="lg" className="text-blue-400" />
              Full AI Analysis
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
                    {section.content}
                  </p>
                  {section.actions && (
                    <div className="pl-10 space-y-2 mt-3">
                      <p className="text-xs font-medium text-muted-foreground uppercase">Recommended Actions:</p>
                      {section.actions.map((action) => (
                        <div key={action.id} className="flex items-center gap-2 text-sm">
                          <Check className="h-4 w-4 text-emerald-400" />
                          <span>{action.label}</span>
                          <span className={cn(
                            "text-[10px] px-1.5 py-0.5 rounded-full",
                            action.priority === "high" ? "bg-red-500/10 text-red-400" :
                            action.priority === "medium" ? "bg-amber-500/10 text-amber-400" :
                            "bg-blue-500/10 text-blue-400"
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
              Export Report
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Verify Sources Dialog */}
      <Dialog open={showVerifySources} onOpenChange={setShowVerifySources}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Icon name="shield" size="lg" className="text-emerald-400" />
              Source Verification
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
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
                    <Check className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{source.name}</p>
                    <p className="text-xs text-muted-foreground">Last checked {source.timestamp}</p>
                  </div>
                </div>
                <span className="text-xs text-emerald-400 font-medium uppercase">{source.status}</span>
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
