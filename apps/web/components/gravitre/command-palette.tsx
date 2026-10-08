"use client"

import { useEffect, useState, useCallback } from "react"
import { usePathname, useRouter } from "next/navigation"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import {
  dispatchWorkShortcut,
  isEditableTarget,
  isWorkSectionPath,
  markFocusSearchAfterNav,
} from "@/lib/work-page-shortcuts"
import {
  Target,
  Workflow,
  Bot,
  Database,
  FileText,
  Settings,
  Plus,
  Play,
  Search,
  Shield,
  BarChart3,
  Plug,
  Users,
  ArrowRight,
  RotateCcw,
  Clock,
  CheckCircle,
  AlertTriangle,
  GitBranch,
  Zap,
  Home,
  Lightbulb,
  Eye,
  FlaskConical,
  History,
  TrendingUp,
  Activity,
  Layers3,
  Cpu,
  ShieldAlert,
  Rocket,
  Package,
} from "lucide-react"

interface CommandPaletteProps {
  onCreateFromGoal?: () => void
  onShowOptimizations?: () => void
  onPreviewChanges?: () => void
  onStartABTest?: () => void
  onCompareVersions?: () => void
}

export function CommandPalette({ 
  onCreateFromGoal,
  onShowOptimizations,
  onPreviewChanges,
  onStartABTest,
  onCompareVersions,
}: CommandPaletteProps) {
  const [open, setOpen] = useState(false)
  const router = useRouter()
  const pathname = usePathname()
  const { summonWorkspace } = useGravitreAIWorkspace()

  const openUniversalSearch = useCallback(() => {
    if (pathname === "/search") {
      dispatchWorkShortcut("focus-search")
      return
    }
    markFocusSearchAfterNav()
    router.push("/search")
  }, [pathname, router])

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        if (isEditableTarget(e.target)) return
        e.preventDefault()

        if (pathname === "/search") {
          dispatchWorkShortcut("focus-search")
          return
        }
        if (isWorkSectionPath(pathname)) {
          openUniversalSearch()
          return
        }

        setOpen((open) => !open)
      }
    }

    document.addEventListener("keydown", down)
    return () => document.removeEventListener("keydown", down)
  }, [pathname, openUniversalSearch])

  const runCommand = useCallback((command: () => void) => {
    setOpen(false)
    command()
  }, [])

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Type a command or search..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Quick actions">
          <CommandItem onSelect={() => runCommand(() => summonWorkspace())}>
            <ArrowRight className="mr-2 h-4 w-4 text-[color:var(--g-emerald-deep)]" />
            <span>Start chat</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => summonWorkspace())}>
            <Bot className="mr-2 h-4 w-4 text-success-text" />
            <span>Open Gravitre AI</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/agents/new"))}>
            <Plus className="mr-2 h-4 w-4" />
            <span>Create agent</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/workflows"))}>
            <Play className="mr-2 h-4 w-4" />
            <span>Run workflow</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push(APP_ROUTES.approvals))}>
            <CheckCircle className="mr-2 h-4 w-4 text-warning-text" />
            <span>View approvals</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Search">
          <CommandItem onSelect={() => runCommand(openUniversalSearch)}>
            <Search className="mr-2 h-4 w-4 text-success-text" />
            <span>Universal search</span>
            <span className="ml-2 text-xs text-muted-foreground">Find records — not chat</span>
            <CommandShortcut>⌘K</CommandShortcut>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Goal Commands */}
        <CommandGroup heading="Goals">
          <CommandItem
            onSelect={() => runCommand(() => {
              onCreateFromGoal?.()
            })}
          >
            <Target className="mr-2 h-4 w-4 text-success-text" />
            <span>Create from Goal</span>
            <CommandShortcut>G</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/workflows"))}
          >
            <GitBranch className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>Generate Workflow from Prompt</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/goals"))}
          >
            <BarChart3 className="mr-2 h-4 w-4 text-info" />
            <span>Show goal progress</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {})}
          >
            <RotateCcw className="mr-2 h-4 w-4 text-warning-text" />
            <span>Regenerate plan</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Insights & learning">
          <CommandItem onSelect={() => runCommand(() => router.push(APP_ROUTES.intelligence))}>
            <GitBranch className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>{SURFACE_COPY.insights.title}</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push(APP_ROUTES.learning))}>
            <GitBranch className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>{SURFACE_COPY.learning.title}</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push(APP_ROUTES.builtInModels))}>
            <Cpu className="mr-2 h-4 w-4 text-success-text" />
            <span>{SURFACE_COPY.builtInModels.title}</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push(APP_ROUTES.intelligenceData))}>
            <Layers3 className="mr-2 h-4 w-4 text-[color:var(--g-emerald-deep)]" />
            <span>{SURFACE_COPY.intelligenceData.title}</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push(APP_ROUTES.training))}>
            <Layers3 className="mr-2 h-4 w-4 text-[color:var(--g-emerald-deep)]" />
            <span>{SURFACE_COPY.trainingInstructions.title}</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push(APP_ROUTES.models))}>
            <Layers3 className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>{SURFACE_COPY.models.title}</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Optimization Commands */}
        <CommandGroup heading="Optimization">
          <CommandItem
            onSelect={() => runCommand(() => {
              onShowOptimizations?.()
            })}
          >
            <Lightbulb className="mr-2 h-4 w-4 text-[color:var(--g-signal)]" />
            <span>Show optimization insights</span>
            <CommandShortcut>O</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              onPreviewChanges?.()
            })}
          >
            <Eye className="mr-2 h-4 w-4 text-info" />
            <span>Preview recommended changes</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <TrendingUp className="mr-2 h-4 w-4 text-success-text" />
            <span>Apply top optimization</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              onStartABTest?.()
            })}
          >
            <FlaskConical className="mr-2 h-4 w-4 text-warning-text" />
            <span>Start A/B Test</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              onCompareVersions?.()
            })}
          >
            <History className="mr-2 h-4 w-4 text-info" />
            <span>Compare workflow versions</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <RotateCcw className="mr-2 h-4 w-4 text-danger-text" />
            <span>Roll back workflow</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <Activity className="mr-2 h-4 w-4 text-intelligence-text" />
            <span>View agent performance</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Workflow Commands */}
        <CommandGroup heading="Workflows">
          <CommandItem
            onSelect={() => runCommand(() => router.push("/workflows/new/builder"))}
          >
            <Plus className="mr-2 h-4 w-4" />
            <span>New workflow</span>
            <CommandShortcut>N</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/workflows"))}
          >
            <Workflow className="mr-2 h-4 w-4" />
            <span>View all workflows</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push(`${APP_ROUTES.activity}?tab=failures`))}
          >
            <ShieldAlert className="mr-2 h-4 w-4 text-danger-text" />
            <span>Failure alerts</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <Shield className="mr-2 h-4 w-4 text-danger-text" />
            <span>Add approval gate</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <GitBranch className="mr-2 h-4 w-4 text-[color:var(--g-signal)]" />
            <span>Add decision node</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <Users className="mr-2 h-4 w-4 text-warning-text" />
            <span>Add Agent Council</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Navigation */}
        <CommandGroup heading="Navigate">
          <CommandItem
            onSelect={() => runCommand(() => router.push(APP_ROUTES.home))}
          >
            <Home className="mr-2 h-4 w-4" />
            <span>Home</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push(APP_ROUTES.welcome))}
          >
            <Rocket className="mr-2 h-4 w-4 text-success-text" />
            <span>Getting started</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => summonWorkspace())}
          >
            <ArrowRight className="mr-2 h-4 w-4 text-[color:var(--g-emerald-deep)]" />
            <span>Open Gravitre AI</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push(APP_ROUTES.marketplace))}
          >
            <Package className="mr-2 h-4 w-4 text-info" />
            <span>Marketplace</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push(APP_ROUTES.intelligence))}
          >
            <GitBranch className="mr-2 h-4 w-4 text-muted-foreground" />
            <span>{SURFACE_COPY.insights.title}</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push(APP_ROUTES.revenueRisk))}
          >
            <ShieldAlert className="mr-2 h-4 w-4 text-danger-text" />
            <span>Revenue risk radar</span>
          </CommandItem>

          <CommandItem
            onSelect={() => runCommand(() => router.push("/agents"))}
          >
            <Bot className="mr-2 h-4 w-4" />
            <span>Agents</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/connectors"))}
          >
            <Plug className="mr-2 h-4 w-4" />
            <span>Connectors</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/sources"))}
          >
            <Database className="mr-2 h-4 w-4" />
            <span>Data sources</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/deliverables"))}
          >
            <FileText className="mr-2 h-4 w-4" />
            <span>Deliverables</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push(APP_ROUTES.activity))}
          >
            <Play className="mr-2 h-4 w-4" />
            <span>Runs</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Quick Actions */}
        <CommandGroup heading="Actions">
          <CommandItem onSelect={() => runCommand(() => {})}>
            <Plug className="mr-2 h-4 w-4 text-warning-text" />
            <span>Add missing connector</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/deliverables"))}>
            <FileText className="mr-2 h-4 w-4 text-success-text" />
            <span>Open goal deliverables</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/settings"))}
          >
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}

// Export a hook to trigger the command palette from anywhere
export function useCommandPalette() {
  const triggerCommandPalette = useCallback(() => {
    const event = new KeyboardEvent("keydown", {
      key: "k",
      metaKey: true,
      bubbles: true,
    })
    document.dispatchEvent(event)
  }, [])

  return { triggerCommandPalette }
}
