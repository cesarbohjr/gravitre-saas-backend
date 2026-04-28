"use client"

import {
  Bot,
  Zap,
  Database,
  ListChecks,
  ShieldCheck,
  BarChart3,
  History,
  Layers,
  Settings,
  Search,
  Bell,
  User,
  Play,
  GitBranch,
  Plug,
  Brain,
  AlertTriangle,
  XCircle,
  Loader2,
  CheckCircle,
  Clock,
  Circle,
  Network,
  RefreshCw,
  Sparkles,
  ChevronRight,
  ChevronDown,
  Eye,
  FileQuestion,
  Timer,
  Bug,
  CloudUpload,
  Code,
  Lightbulb,
  AlertCircle,
  CheckCheck,
  Target,
  Plus,
  X,
  MoreHorizontal,
  MoreVertical,
  Pause,
  Trash2,
  Copy,
  Pencil,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  LogOut,
  Home,
  Mail,
  Phone,
  Link,
  Share2,
  Download,
  Upload,
  Filter,
  ArrowUpDown,
  Calendar,
  Tag,
  Bookmark,
  Heart,
  Star,
  Lock,
  Unlock,
  Key,
  HelpCircle,
  Info,
  MessageCircle,
  Send,
  File,
  Folder,
  Image,
  Video,
  Mic,
  Headphones,
  Wifi,
  WifiOff,
  Power,
  Moon,
  Sun,
  Languages,
  Globe,
  MapPin,
  CreditCard,
  Receipt,
  Wallet,
  Building2,
  UserCircle,
  Users,
  Users2,
  Handshake,
  Trophy,
  Medal,
TrendingUp,
  TrendingDown,
  PieChart,
  Table,
  LayoutGrid,
  Rows3,
  Columns3,
  Grid3X3,
  ChevronUp,
  ChevronLeft,
  Maximize2,
  Minimize2,
  Command,
  Terminal,
  Cpu,
  HardDrive,
  CloudCheck,
  Activity,
  Gauge,
  SlidersHorizontal,
  Crosshair,
  Box,
  Package,
  Rocket,
  FlaskConical,
  Atom,
  Workflow,
  Hexagon,
  Shield,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"

// Icon size scale (strict)
export const iconSizes = {
  xs: 14,
  sm: 16,
  md: 18,
  lg: 20,
  xl: 24,
  "2xl": 32,
} as const

export type IconSize = keyof typeof iconSizes

// Semantic icon map using Lucide icons
export const iconMap = {
  // Navigation
  ai: Bot,
  assistant: Bot,
  agents: Users,
  workflows: Workflow,
  automations: Workflow,
  connectors: Plug,
  apps: Plug,
  data: Database,
  database: Database,
  sources: Database,
  runs: Play,
  run: Play,
  tasks: ListChecks,
  approvals: CheckCircle,
  metrics: BarChart3,
  dashboard: BarChart3,
  audit: History,
  history: History,
  environments: Layers,
  workspaces: Layers,
  settings: Settings,
  search: Search,
  notifications: Bell,
  user: User,
  profile: UserCircle,

  // AI & Intelligence
  brain: Brain,
  sparkles: Sparkles,
  magic: Sparkles,
  insight: Lightbulb,
  analyze: Target,
  target: Target,
  aiAnalysis: Brain,
  confidence: Gauge,
  reasoning: Brain,
  
  // Workflow & Structure
  workflow: Workflow,
  branch: GitBranch,
  network: Network,
  sync: RefreshCw,
  refresh: RefreshCw,

  // Status States
  success: CheckCircle,
  completed: CheckCheck,
  checkCircle: CheckCircle,
  check: CheckCircle,
  failed: XCircle,
  warning: AlertTriangle,
  error: AlertCircle,
  running: Loader2,
  pending: Clock,
  queued: Clock,
  queue: Clock,
  clock: Clock,
  eye: Eye,
  view: Eye,
  active: Circle,
  draft: FileQuestion,
  latency: Timer,
  activity: Activity,
  pulse: Activity,
  
// Actions
  add: Plus,
  plus: Plus,
  remove: X,
  close: X,
  more: MoreHorizontal,
  moreVertical: MoreVertical,
  play: Play,
  pause: Pause,
  delete: Trash2,
  copy: Copy,
  duplicate: Copy,
  edit: Pencil,
  expand: ChevronRight,
  collapse: ChevronDown,
  back: ArrowLeft,
  forward: ArrowRight,
  up: ArrowUp,
  down: ArrowDown,
  trendUp: TrendingUp,
  trendDown: TrendingDown,
  logout: LogOut,
  signOut: LogOut,
  
  // UI Elements
  home: Home,
  link: Link,
  share: Share2,
  social: Share2,
  download: Download,
  upload: Upload,
  filter: Filter,
  sort: ArrowUpDown,
  bookmark: Bookmark,
  tag: Tag,
  calendar: Calendar,
  heart: Heart,
  star: Star,
  spinner: Loader2,
  loading: Loader2,
  
  // Security
  security: Shield,
  shield: Shield,
  shieldCheck: ShieldCheck,
  lock: Lock,
  unlock: Unlock,
  key: Key,
  
  // Communication
  help: HelpCircle,
  info: Info,
  chat: MessageCircle,
  message: MessageCircle,
  send: Send,
  mail: Mail,
  
  // Files & Documents
  file: File,
  folder: Folder,
  
  // Connections
  connect: Plug,
  trash: Trash2,
  phone: Phone,
  
  // Files & Media
  image: Image,
  video: Video,
  audio: Mic,
  microphone: Mic,
  headphones: Headphones,
  
  // System & Tech
  wifi: Wifi,
  wifiOff: WifiOff,
  power: Power,
  dark: Moon,
  light: Sun,
  language: Languages,
  globe: Globe,
  location: MapPin,
  
  // Business
  billing: CreditCard,
  payment: CreditCard,
  receipt: Receipt,
  wallet: Wallet,
  building: Building2,
  company: Building2,
  team: Users2,
  users: Users,
  handshake: Handshake,
  trophy: Trophy,
  medal: Medal,
  
  // Charts & Data
  chart: TrendingUp,
  chartLine: TrendingUp,
  chartPie: PieChart,
  table: Table,
  grid: LayoutGrid,
  layoutGrid: LayoutGrid,
  rows: Rows3,
  columns: Columns3,
  tiles: Grid3X3,
  
  // Arrows & Direction
  chevronUp: ChevronUp,
  chevronDown: ChevronDown,
  chevronLeft: ChevronLeft,
  chevronRight: ChevronRight,
  caretRight: ChevronRight,
  caretDown: ChevronDown,
  caretUp: ChevronUp,
  caretLeft: ChevronLeft,
  maximize: Maximize2,
  minimize: Minimize2,
  
  // Dev & System
  command: Command,
  terminal: Terminal,
  cpu: Cpu,
  storage: HardDrive,
  cloud: CloudCheck,
  cloudUpload: CloudUpload,
  gauge: Gauge,
  sliders: SlidersHorizontal,
  crosshair: Crosshair,
  execution: Zap,
  
  // Objects
  box: Box,
  package: Package,
  rocket: Rocket,
  flask: FlaskConical,
  atom: Atom,
  hexagon: Hexagon,
  code: Code,
  bug: Bug,
  
  // Environment
  production: Rocket,
  staging: FlaskConical,
} as const

export type IconName = keyof typeof iconMap

// Icon component props
interface IconProps {
  name: IconName
  size?: IconSize
  className?: string
  emphasis?: boolean
}

// Main Icon component
export function Icon({ name, size = "md", className, emphasis = false }: IconProps) {
  const IconComponent = iconMap[name]
  const sizeValue = iconSizes[size]
  
  if (!IconComponent) {
    console.warn(`[v0] Icon "${name}" not found in icon map`)
    return null
  }
  
  return (
    <IconComponent 
      size={sizeValue}
      className={cn(
        "shrink-0",
        emphasis && "stroke-[2.5]",
        className
      )}
    />
  )
}

// Status icon helper
export function StatusIcon({ 
  status, 
  size = "sm",
  className 
}: { 
  status: "success" | "failed" | "warning" | "error" | "running" | "pending" | "active" | "draft" | "paused" | "completed"
  size?: IconSize
  className?: string 
}) {
  const statusIconMap: Record<string, IconName> = {
    success: "success",
    completed: "completed",
    failed: "failed",
    warning: "warning",
    error: "error",
    running: "running",
    pending: "pending",
    active: "active",
    draft: "draft",
    paused: "pause",
  }
  
  const statusColorMap: Record<string, string> = {
    success: "text-emerald-500",
    completed: "text-emerald-500",
    failed: "text-red-500",
    warning: "text-amber-500",
    error: "text-red-500",
    running: "text-blue-500 animate-spin",
    pending: "text-muted-foreground",
    active: "text-emerald-500",
    draft: "text-muted-foreground",
    paused: "text-amber-500",
  }
  
  return (
    <Icon 
      name={statusIconMap[status] as IconName} 
      size={size}
      className={cn(statusColorMap[status], className)}
    />
  )
}

// Environment icon helper
export function EnvironmentIcon({ 
  environment,
  size = "sm",
  className 
}: { 
  environment: "production" | "staging" | "development"
  size?: IconSize
  className?: string 
}) {
  const envIconMap: Record<string, IconName> = {
    production: "rocket",
    staging: "flask",
    development: "code",
  }
  
  const envColorMap: Record<string, string> = {
    production: "text-emerald-500",
    staging: "text-amber-500", 
    development: "text-blue-500",
  }
  
  return (
    <Icon 
      name={envIconMap[environment] as IconName}
      size={size}
      className={cn(envColorMap[environment], className)}
    />
  )
}

// Helper to get the raw icon component
export function getIconComponent(name: IconName): LucideIcon {
  return iconMap[name]
}

// Get status icon and color
export function getStatusIcon(status: string): { icon: LucideIcon; color: string } {
  const map: Record<string, { icon: LucideIcon; color: string }> = {
    success: { icon: CheckCircle, color: "text-emerald-500" },
    completed: { icon: CheckCheck, color: "text-emerald-500" },
    failed: { icon: XCircle, color: "text-red-500" },
    warning: { icon: AlertTriangle, color: "text-amber-500" },
    error: { icon: AlertCircle, color: "text-red-500" },
    running: { icon: Loader2, color: "text-blue-500" },
    pending: { icon: Clock, color: "text-muted-foreground" },
    active: { icon: Circle, color: "text-emerald-500" },
    draft: { icon: FileQuestion, color: "text-muted-foreground" },
    paused: { icon: Pause, color: "text-amber-500" },
  }
  return map[status] || { icon: Circle, color: "text-muted-foreground" }
}

// Export raw icons for cases where direct imports are needed
export { iconMap as Icons }
