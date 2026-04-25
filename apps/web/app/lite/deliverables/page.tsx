"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader, StatsGrid, StatCard } from "@/components/gravitre/page-header"
import {
  MorphingBackground,
  GlowOrb,
  ParticleField,
  StatusBeacon,
  AnimatedCounter,
  ActivityIndicator
} from "@/components/gravitre/premium-effects"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { 
  Mail, 
  MessageSquare, 
  Database, 
  Download, 
  Check, 
  Clock, 
  Package,
  Eye,
  Pencil,
  ExternalLink,
  FileText,
  Users,
  Share2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Sparkles,
  Zap,
  TrendingUp,
  Send
} from "lucide-react"

// Delivery status types
type DeliveryStatus = "draft" | "ready" | "delivered" | "partially_delivered" | "failed"

// Action taken types
interface ActionTaken {
  id: string
  platform: string
  action: string
  destination?: string
  timestamp: Date
  status: "success" | "failed" | "pending"
}

// Delivery history entry
interface DeliveryHistoryEntry {
  id: string
  timestamp: Date
  action: string
  destination: string
  status: "success" | "failed" | "pending"
}

interface Deliverable {
  id: string
  title: string
  type: "emails" | "segment" | "report" | "social" | "presentation"
  agent: string
  taskTitle: string
  confidence: number
  createdAt: string
  status: DeliveryStatus
  outputs: {
    type: string
    title: string
    preview?: string
    count?: number
    pages?: number
  }[]
  actionsTaken: ActionTaken[]
  deliveryHistory: DeliveryHistoryEntry[]
}

const deliverables: Deliverable[] = [
  {
    id: "1",
    title: "Email Sequence - Product Launch",
    type: "emails",
    agent: "Marketing Agent",
    taskTitle: "Q3 Healthcare Campaign",
    confidence: 94,
    createdAt: "10 min ago",
    status: "ready",
    outputs: [
      { type: "email", title: "Introduction Email", preview: "Introducing our new compliance features..." },
      { type: "email", title: "Follow-up #1", preview: "Did you get a chance to review..." },
      { type: "email", title: "Follow-up #2", preview: "I wanted to share a case study..." },
    ],
    actionsTaken: [
      { id: "a1", platform: "Gravitre", action: "Stored in Deliverables", timestamp: new Date(Date.now() - 1000 * 60 * 10), status: "success" },
    ],
    deliveryHistory: [
      { id: "h1", timestamp: new Date(Date.now() - 1000 * 60 * 10), action: "Created", destination: "Gravitre", status: "success" },
    ],
  },
  {
    id: "2",
    title: "Enterprise Segment",
    type: "segment",
    agent: "Sales Agent",
    taskTitle: "Lead Scoring Update",
    confidence: 88,
    createdAt: "1 hour ago",
    status: "delivered",
    outputs: [
      { type: "segment", title: "High-Value Leads", count: 234 },
      { type: "segment", title: "Ready to Buy", count: 47 },
    ],
    actionsTaken: [
      { id: "a1", platform: "HubSpot", action: "Campaign created", timestamp: new Date(Date.now() - 1000 * 60 * 45), status: "success" },
      { id: "a2", platform: "Email", action: "Sent to your inbox", timestamp: new Date(Date.now() - 1000 * 60 * 45), status: "success" },
      { id: "a3", platform: "Gravitre", action: "Stored in Deliverables", timestamp: new Date(Date.now() - 1000 * 60 * 60), status: "success" },
    ],
    deliveryHistory: [
      { id: "h1", timestamp: new Date(Date.now() - 1000 * 60 * 60), action: "Created", destination: "Gravitre", status: "success" },
      { id: "h2", timestamp: new Date(Date.now() - 1000 * 60 * 45), action: "Sent email", destination: "john@acme.com", status: "success" },
      { id: "h3", timestamp: new Date(Date.now() - 1000 * 60 * 45), action: "Created campaign", destination: "HubSpot", status: "success" },
    ],
  },
  {
    id: "3",
    title: "Competitor Analysis Report",
    type: "report",
    agent: "Research Agent",
    taskTitle: "Competitor Research",
    confidence: 91,
    createdAt: "2 hours ago",
    status: "delivered",
    outputs: [
      { type: "report", title: "Full Analysis", pages: 12 },
    ],
    actionsTaken: [
      { id: "a1", platform: "Slack", action: "Posted to #marketing", timestamp: new Date(Date.now() - 1000 * 60 * 60), status: "success" },
      { id: "a2", platform: "Gravitre", action: "Stored in Deliverables", timestamp: new Date(Date.now() - 1000 * 60 * 120), status: "success" },
    ],
    deliveryHistory: [
      { id: "h1", timestamp: new Date(Date.now() - 1000 * 60 * 120), action: "Created", destination: "Gravitre", status: "success" },
      { id: "h2", timestamp: new Date(Date.now() - 1000 * 60 * 60), action: "Posted message", destination: "Slack #marketing", status: "success" },
    ],
  },
  {
    id: "4",
    title: "Social Media Campaign",
    type: "social",
    agent: "Marketing Agent",
    taskTitle: "Brand Awareness Q3",
    confidence: 85,
    createdAt: "3 hours ago",
    status: "partially_delivered",
    outputs: [
      { type: "social", title: "LinkedIn Posts", count: 5 },
      { type: "social", title: "Twitter Threads", count: 3 },
    ],
    actionsTaken: [
      { id: "a1", platform: "Slack", action: "Posted to #social", timestamp: new Date(Date.now() - 1000 * 60 * 160), status: "success" },
      { id: "a2", platform: "HubSpot", action: "Campaign creation failed", timestamp: new Date(Date.now() - 1000 * 60 * 155), status: "failed" },
      { id: "a3", platform: "Gravitre", action: "Stored in Deliverables", timestamp: new Date(Date.now() - 1000 * 60 * 180), status: "success" },
    ],
    deliveryHistory: [
      { id: "h1", timestamp: new Date(Date.now() - 1000 * 60 * 180), action: "Created", destination: "Gravitre", status: "success" },
      { id: "h2", timestamp: new Date(Date.now() - 1000 * 60 * 160), action: "Posted message", destination: "Slack #social", status: "success" },
      { id: "h3", timestamp: new Date(Date.now() - 1000 * 60 * 155), action: "Create campaign", destination: "HubSpot", status: "failed" },
    ],
  },
]

const typeIcons = {
  emails: Mail,
  segment: Users,
  report: FileText,
  social: Share2,
  presentation: FileText,
}

const platformIcons: Record<string, React.ElementType> = {
  Email: Mail,
  Slack: MessageSquare,
  HubSpot: Database,
  CRM: Database,
  Gravitre: Package,
  Download: Download,
}

const statusConfig: Record<DeliveryStatus, { label: string; color: string; bg: string; icon: React.ElementType }> = {
  draft: { label: "Draft", color: "text-muted-foreground", bg: "bg-secondary", icon: Pencil },
  ready: { label: "Ready", color: "text-emerald-500", bg: "bg-emerald-500/10", icon: Sparkles },
  delivered: { label: "Delivered", color: "text-blue-500", bg: "bg-blue-500/10", icon: CheckCircle2 },
  partially_delivered: { label: "Partially Delivered", color: "text-amber-500", bg: "bg-amber-500/10", icon: AlertCircle },
  failed: { label: "Failed", color: "text-red-500", bg: "bg-red-500/10", icon: XCircle },
}

function formatRelativeTime(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)

  if (diffMins < 1) return "Just now"
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return date.toLocaleDateString()
}

function formatTimestamp(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function LiteDeliverablesPage() {
  const [selectedDeliverable, setSelectedDeliverable] = useState<string | null>("1")
  const [showDeliveryModal, setShowDeliveryModal] = useState(false)
  const [deliveryPlatform, setDeliveryPlatform] = useState<string | null>(null)
  const [isDelivering, setIsDelivering] = useState(false)
  const [deliveryComplete, setDeliveryComplete] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [activeTab, setActiveTab] = useState("outputs")

  useEffect(() => {
    setMounted(true)
  }, [])

  const selected = deliverables.find(d => d.id === selectedDeliverable)
  const StatusIcon = selected ? statusConfig[selected.status].icon : CheckCircle2

  const handleDeliver = async (platform: string) => {
    setDeliveryPlatform(platform)
    setIsDelivering(true)
    await new Promise(resolve => setTimeout(resolve, 2000))
    setIsDelivering(false)
    setDeliveryComplete(true)
  }

  const readyCount = deliverables.filter((d) => d.status === "ready").length
  const deliveredCount = deliverables.filter((d) => d.status === "delivered").length

  return (
    <AppShell title="Deliverables">
      <div className="relative flex flex-col lg:flex-row h-full overflow-hidden">
        {/* Premium ambient background */}
        <div className="absolute inset-0 pointer-events-none z-0">
          <MorphingBackground colors={["emerald", "teal", "cyan"]} />
          <div className="absolute inset-0 bg-background/90 backdrop-blur-3xl" />
        </div>
        
        {/* Ambient orbs */}
        <div className="absolute top-20 right-1/4 pointer-events-none z-0">
          <GlowOrb size={250} color="emerald" intensity={0.2} />
        </div>
        <div className="absolute bottom-40 left-10 pointer-events-none z-0">
          <GlowOrb size={180} color="teal" intensity={0.15} />
        </div>

        {/* Left Panel - List */}
        <div className="relative z-10 w-full lg:w-[420px] border-b lg:border-b-0 lg:border-r border-border/50 flex flex-col bg-card/30 backdrop-blur-sm">
          <PageHeader
            title="Deliverables"
            description="Review and deliver AI outputs"
            icon={Package}
            iconColor="from-emerald-500/20 to-teal-500/20"
          >
            <StatsGrid columns={3}>
              <StatCard label="Total" value={deliverables.length} />
              <StatCard label="Ready" value={readyCount} variant="success" />
              <StatCard label="Delivered" value={deliveredCount} variant="info" />
            </StatsGrid>
          </PageHeader>
            <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-on-hover">
              {/* Particles when items are ready */}
              {readyCount > 0 && (
                <ParticleField count={15} color="emerald" interactive={false} className="opacity-30" />
              )}
              
              <AnimatePresence mode="popLayout">
                {deliverables.map((item, index) => {
                  const TypeIcon = typeIcons[item.type]
                  const ItemStatusIcon = statusConfig[item.status].icon
                  
                  return (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 20, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ delay: index * 0.05, type: "spring", stiffness: 100 }}
                      whileHover={{ scale: 1.02, y: -2 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <Card
                        onClick={() => setSelectedDeliverable(item.id)}
                        className={cn(
                          "p-4 cursor-pointer transition-all relative overflow-hidden",
                          selectedDeliverable === item.id
                            ? "border-emerald-500/50 bg-gradient-to-br from-emerald-500/10 to-teal-500/5 ring-2 ring-emerald-500/20 shadow-lg shadow-emerald-500/10"
                            : "border-border/50 hover:border-border bg-card/50 backdrop-blur-sm hover:shadow-md"
                        )}
                      >
                        {/* Top accent for ready items */}
                        {item.status === "ready" && (
                          <motion.div 
                            className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-500"
                            animate={{ backgroundPosition: ["0% 0%", "100% 0%", "0% 0%"] }}
                            transition={{ duration: 3, repeat: Infinity }}
                            style={{ backgroundSize: "200% 100%" }}
                          />
                        )}
                        
                        <div className="flex items-start gap-3">
                          <motion.div 
                            className={cn(
                              "w-11 h-11 rounded-xl flex items-center justify-center shrink-0 relative",
                              statusConfig[item.status].bg
                            )}
                            animate={item.status === "ready" ? { scale: [1, 1.05, 1] } : {}}
                            transition={{ duration: 2, repeat: Infinity }}
                          >
                            <TypeIcon className={cn("w-5 h-5", statusConfig[item.status].color)} />
                            {item.status === "ready" && (
                              <motion.div 
                                className="absolute inset-0 rounded-xl border border-emerald-400"
                                animate={{ scale: [1, 1.3], opacity: [0.6, 0] }}
                                transition={{ duration: 1.5, repeat: Infinity }}
                              />
                            )}
                          </motion.div>
                          <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-sm text-foreground truncate">{item.title}</h3>
                            <p className="text-xs text-muted-foreground">{item.agent}</p>
                            <div className="flex items-center gap-2 mt-2 flex-wrap">
                              <span className="text-xs text-muted-foreground flex items-center gap-1">
                                <Clock className="h-3 w-3" />
                                {item.createdAt}
                              </span>
                              <Badge 
                                variant="outline" 
                                className={cn(
                                  "text-[10px] font-semibold",
                                  statusConfig[item.status].color,
                                  statusConfig[item.status].bg.replace("/10", "/20"),
                                  `border-${statusConfig[item.status].color.replace("text-", "")}/30`
                                )}
                              >
                                <StatusBeacon 
                                  status={item.status === "ready" ? "active" : item.status === "delivered" ? "idle" : item.status === "failed" ? "error" : "processing"} 
                                  size="sm" 
                                  pulse={item.status === "ready"}
                                />
                                <span className="ml-1.5">{statusConfig[item.status].label}</span>
                              </Badge>
                            </div>
                        
                        {/* Actions summary */}
                        {item.actionsTaken.length > 0 && (
                          <div className="flex items-center gap-1 mt-2">
                            {item.actionsTaken.slice(0, 3).map((action) => {
                              const PlatformIcon = platformIcons[action.platform] || Package
                              return (
                                <div 
                                  key={action.id}
                                  className={cn(
                                    "w-5 h-5 rounded-full flex items-center justify-center",
                                    action.status === "success" && "bg-emerald-500/10",
                                    action.status === "failed" && "bg-red-500/10",
                                    action.status === "pending" && "bg-amber-500/10"
                                  )}
                                >
                                  <PlatformIcon className={cn(
                                    "w-2.5 h-2.5",
                                    action.status === "success" && "text-emerald-500",
                                    action.status === "failed" && "text-red-500",
                                    action.status === "pending" && "text-amber-500"
                                  )} />
                                </div>
                              )
                            })}
                            {item.actionsTaken.length > 3 && (
                              <span className="text-[10px] text-muted-foreground">
                                +{item.actionsTaken.length - 3}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-semibold text-foreground">{item.confidence}%</div>
                        <div className="text-[10px] text-muted-foreground">confidence</div>
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          </div>

          {/* Right Panel - Detail */}
          <div className="relative z-10 flex-1 p-4 sm:p-6 bg-card/20 backdrop-blur-sm">
            {/* Top gradient accent */}
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500" />
            
            {selected ? (
              <motion.div
                key={selected.id}
                initial={{ opacity: 0, x: 30, scale: 0.98 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                transition={{ type: "spring", stiffness: 100 }}
              >
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
                  <div>
                    <div className="flex flex-wrap items-center gap-3 mb-2">
                      <h2 className="text-lg sm:text-xl font-bold text-foreground">{selected.title}</h2>
                      <Badge 
                        variant="outline" 
                        className={cn(
                          statusConfig[selected.status].color,
                          statusConfig[selected.status].bg,
                          "border-current/30"
                        )}
                      >
                        <StatusIcon className="w-3 h-3 mr-1" />
                        {statusConfig[selected.status].label}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 sm:gap-4 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Icon name="ai" size="xs" />
                        {selected.agent}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {selected.createdAt}
                      </span>
                    </div>
                  </div>
                  
                  {/* Confidence Ring */}
                  <div className="relative w-16 h-16 shrink-0 hidden sm:block">
                    <svg className="w-16 h-16 -rotate-90">
                      <circle cx="32" cy="32" r="28" fill="none" stroke="currentColor" strokeWidth="4" className="text-secondary" />
                      <circle 
                        cx="32" cy="32" r="28" fill="none" stroke="currentColor" strokeWidth="4" 
                        className="text-emerald-500"
                        strokeDasharray={`${selected.confidence * 1.76} 176`}
                        strokeLinecap="round"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-sm font-bold text-foreground">{selected.confidence}%</span>
                    </div>
                  </div>
                </div>

                {/* Tabs for different sections */}
                <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-6">
                  <TabsList className="grid w-full grid-cols-3 h-auto p-1">
                    <TabsTrigger value="outputs" className="text-xs sm:text-sm py-2">
                      Outputs
                    </TabsTrigger>
                    <TabsTrigger value="actions" className="text-xs sm:text-sm py-2">
                      Actions Taken
                    </TabsTrigger>
                    <TabsTrigger value="history" className="text-xs sm:text-sm py-2">
                      Delivery History
                    </TabsTrigger>
                  </TabsList>

                  {/* Outputs Tab */}
                  <TabsContent value="outputs" className="mt-4">
                    <div className="space-y-3">
                      {selected.outputs.map((output, index) => (
                        <Card key={index} className="p-4 border-border/50">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
                                {(() => {
                                  const OutputIcon = typeIcons[selected.type]
                                  return <OutputIcon className="w-5 h-5 text-muted-foreground" />
                                })()}
                              </div>
                              <div>
                                <h4 className="font-medium text-foreground text-sm">{output.title}</h4>
                                {output.preview && (
                                  <p className="text-xs text-muted-foreground truncate max-w-[200px] sm:max-w-md">{output.preview}</p>
                                )}
                                {output.count !== undefined && (
                                  <p className="text-xs text-muted-foreground">{output.count} records</p>
                                )}
                                {output.pages !== undefined && (
                                  <p className="text-xs text-muted-foreground">{output.pages} pages</p>
                                )}
                              </div>
                            </div>
                            <Button variant="ghost" size="sm">
                              <Eye className="w-4 h-4" />
                            </Button>
                          </div>
                        </Card>
                      ))}
                    </div>
                  </TabsContent>

                  {/* Actions Taken Tab */}
                  <TabsContent value="actions" className="mt-4">
                    <Card className="border-border/50 overflow-hidden">
                      <div className="px-4 py-3 border-b border-border bg-secondary/30">
                        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                          What Gravitre Did
                        </h3>
                      </div>
                      <div className="divide-y divide-border/50">
                        {selected.actionsTaken.map((action) => {
                          const PlatformIcon = platformIcons[action.platform] || Package
                          return (
                            <div key={action.id} className="p-4 flex items-center gap-4">
                              <div className={cn(
                                "w-10 h-10 rounded-lg flex items-center justify-center shrink-0",
                                action.status === "success" && "bg-emerald-500/10",
                                action.status === "failed" && "bg-red-500/10",
                                action.status === "pending" && "bg-amber-500/10"
                              )}>
                                <PlatformIcon className={cn(
                                  "w-5 h-5",
                                  action.status === "success" && "text-emerald-500",
                                  action.status === "failed" && "text-red-500",
                                  action.status === "pending" && "text-amber-500"
                                )} />
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-foreground">{action.action}</p>
                                <p className="text-xs text-muted-foreground">{action.platform}</p>
                              </div>
                              <div className="text-right shrink-0">
                                <div className={cn(
                                  "inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs",
                                  action.status === "success" && "bg-emerald-500/10 text-emerald-500",
                                  action.status === "failed" && "bg-red-500/10 text-red-500",
                                  action.status === "pending" && "bg-amber-500/10 text-amber-500"
                                )}>
                                  {action.status === "success" && <Check className="w-3 h-3" />}
                                  {action.status === "failed" && <XCircle className="w-3 h-3" />}
                                  {action.status === "pending" && <Clock className="w-3 h-3" />}
                                  {action.status}
                                </div>
                                <p className="text-[10px] text-muted-foreground mt-1">
                                  {formatRelativeTime(action.timestamp)}
                                </p>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </Card>
                  </TabsContent>

                  {/* Delivery History Tab */}
                  <TabsContent value="history" className="mt-4">
                    <Card className="border-border/50 overflow-hidden">
                      <div className="px-4 py-3 border-b border-border bg-secondary/30">
                        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                          <Clock className="w-4 h-4 text-muted-foreground" />
                          Delivery History
                        </h3>
                      </div>
                      <div className="p-4">
                        <div className="relative">
                          {/* Timeline line */}
                          <div className="absolute left-[18px] top-2 bottom-2 w-px bg-border" />
                          
                          <div className="space-y-4">
                            {selected.deliveryHistory.map((entry, index) => (
                              <div key={entry.id} className="relative flex gap-4 pl-10">
                                {/* Timeline dot */}
                                <div className={cn(
                                  "absolute left-[10px] top-0.5 w-4 h-4 rounded-full border-2 border-background",
                                  entry.status === "success" && "bg-emerald-500",
                                  entry.status === "failed" && "bg-red-500",
                                  entry.status === "pending" && "bg-amber-500"
                                )} />
                                
                                <div className="flex-1">
                                  <div className="flex items-center justify-between gap-2">
                                    <p className="text-sm font-medium text-foreground">{entry.action}</p>
                                    <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                                      {formatTimestamp(entry.timestamp)}
                                    </span>
                                  </div>
                                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                                    <ChevronRight className="w-3 h-3" />
                                    {entry.destination}
                                  </p>
                                  {entry.status === "failed" && (
                                    <Badge variant="outline" className="mt-1 text-[10px] text-red-500 border-red-500/30 bg-red-500/10">
                                      <XCircle className="w-2.5 h-2.5 mr-1" />
                                      Failed
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </Card>
                  </TabsContent>
                </Tabs>

                {/* Delivery Options */}
                {selected.status === "ready" && !deliveryComplete && (
                  <div className="border-t border-border pt-6">
                    <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
                      Deliver To
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {[
                        { id: "email", label: "Send to Email", icon: Mail, description: "Push to your inbox" },
                        { id: "slack", label: "Post to Slack", icon: MessageSquare, description: "Send to #marketing" },
                        { id: "crm", label: "Push to CRM", icon: Database, description: "Create in HubSpot" },
                        { id: "export", label: "Export File", icon: Download, description: "Download as document" },
                      ].map((option) => (
                        <Button
                          key={option.id}
                          variant="outline"
                          onClick={() => handleDeliver(option.id)}
                          disabled={isDelivering}
                          className={cn(
                            "h-auto p-4 justify-start gap-3",
                            isDelivering && deliveryPlatform === option.id && "border-emerald-500 bg-emerald-500/5"
                          )}
                        >
                          <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center shrink-0">
                            {isDelivering && deliveryPlatform === option.id ? (
                              <Icon name="spinner" size="md" className="text-emerald-500 animate-spin" />
                            ) : (
                              <option.icon className="w-5 h-5 text-muted-foreground" />
                            )}
                          </div>
                          <div className="text-left">
                            <p className="font-medium text-foreground text-sm">{option.label}</p>
                            <p className="text-xs text-muted-foreground">{option.description}</p>
                          </div>
                        </Button>
                      ))}
                    </div>
                    
                    <div className="flex gap-3 mt-6">
                      <Button className="flex-1 bg-emerald-500 hover:bg-emerald-600 text-white gap-2">
                        <Check className="w-4 h-4" />
                        Approve All
                      </Button>
                      <Button variant="outline" className="gap-2">
                        <Pencil className="w-4 h-4" />
                        Edit
                      </Button>
                    </div>
                  </div>
                )}

                {/* Delivery Complete */}
                {deliveryComplete && (
                  <motion.div 
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="border-t border-border pt-6"
                  >
                    <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-6 text-center">
                      <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-4">
                        <CheckCircle2 className="w-8 h-8 text-emerald-500" />
                      </div>
                      <h3 className="text-lg font-semibold text-foreground mb-2">Delivered Successfully</h3>
                      <p className="text-sm text-muted-foreground mb-4">
                        Your deliverables have been sent to {
                          deliveryPlatform === "email" ? "your email" : 
                          deliveryPlatform === "slack" ? "Slack" : 
                          deliveryPlatform === "crm" ? "HubSpot" : "download"
                        }
                      </p>
                      
                      {/* What was done summary */}
                      <Card className="p-4 bg-background/50 text-left mt-4 max-w-lg mx-auto">
                        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                          What Gravitre Did
                        </h4>
                        <div className="space-y-2">
                          {deliveryPlatform === "email" && (
                            <div className="flex items-center gap-2 text-sm text-foreground">
                              <Mail className="w-4 h-4 text-emerald-500" />
                              Sent email to your inbox
                            </div>
                          )}
                          {deliveryPlatform === "slack" && (
                            <div className="flex items-center gap-2 text-sm text-foreground">
                              <MessageSquare className="w-4 h-4 text-emerald-500" />
                              Posted to Slack #marketing
                            </div>
                          )}
                          {deliveryPlatform === "crm" && (
                            <div className="flex items-center gap-2 text-sm text-foreground">
                              <Database className="w-4 h-4 text-emerald-500" />
                              Created campaign in HubSpot
                            </div>
                          )}
                          {deliveryPlatform === "export" && (
                            <div className="flex items-center gap-2 text-sm text-foreground">
                              <Download className="w-4 h-4 text-emerald-500" />
                              Generated download file
                            </div>
                          )}
                          <div className="flex items-center gap-2 text-sm text-foreground">
                            <Package className="w-4 h-4 text-emerald-500" />
                            Stored in Gravitre Deliverables
                          </div>
                        </div>
                      </Card>
                      
                      <Button 
                        variant="outline" 
                        className="mt-6"
                        onClick={() => {
                          setDeliveryComplete(false)
                          setDeliveryPlatform(null)
                        }}
                      >
                        Done
                      </Button>
                    </div>
                  </motion.div>
                )}

                {/* Already Delivered Summary */}
                {selected.status === "delivered" && selected.actionsTaken.length > 0 && (
                  <div className="border-t border-border pt-6">
                    <Card className="bg-blue-500/5 border-blue-500/20 p-4">
                      <div className="flex items-start gap-4">
                        <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
                          <CheckCircle2 className="w-5 h-5 text-blue-500" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground text-sm">
                            This deliverable has been delivered
                          </p>
                          <div className="flex flex-wrap gap-2 mt-2">
                            {selected.actionsTaken.map((action) => {
                              const PlatformIcon = platformIcons[action.platform] || Package
                              return (
                                <span 
                                  key={action.id}
                                  className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-secondary/50 text-foreground"
                                >
                                  <PlatformIcon className="w-3 h-3" />
                                  {action.action}
                                </span>
                              )
                            })}
                          </div>
                        </div>
                      </div>
                    </Card>
                  </div>
                )}
              </motion.div>
            ) : (
              <div className="flex items-center justify-center h-96 text-muted-foreground">
                Select a deliverable to view details
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
