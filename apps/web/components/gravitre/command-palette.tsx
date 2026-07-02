"use client"

import { useEffect, useState, useCallback } from "react"
import { usePathname, useRouter } from "next/navigation"
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
  Sparkles,
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
  Brain,
  ShieldAlert,
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

        <CommandGroup heading="Search">
          <CommandItem onSelect={() => runCommand(openUniversalSearch)}>
            <Search className="mr-2 h-4 w-4 text-emerald-400" />
            <span>Universal Search</span>
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
            <Target className="mr-2 h-4 w-4 text-emerald-400" />
            <span>Create from Goal</span>
            <CommandShortcut>G</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/workflows"))}
          >
            <Sparkles className="mr-2 h-4 w-4 text-violet-400" />
            <span>Generate Workflow from Prompt</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/goals"))}
          >
            <BarChart3 className="mr-2 h-4 w-4 text-blue-400" />
            <span>Show Goal Progress</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {})}
          >
            <RotateCcw className="mr-2 h-4 w-4 text-amber-400" />
            <span>Regenerate Plan</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Learning & models">
          <CommandItem onSelect={() => runCommand(() => router.push("/intelligence"))}>
            <Sparkles className="mr-2 h-4 w-4 text-violet-400" />
            <span>Intelligence Center</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/admin/intelligence"))}>
            <Sparkles className="mr-2 h-4 w-4 text-violet-400" />
            <span>Org Learning</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/training"))}>
            <Brain className="mr-2 h-4 w-4 text-emerald-400" />
            <span>Agent Training</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/models"))}>
            <Brain className="mr-2 h-4 w-4 text-blue-400" />
            <span>Model Registry</span>
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
            <Lightbulb className="mr-2 h-4 w-4 text-violet-400" />
            <span>Show Optimization Insights</span>
            <CommandShortcut>O</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              onPreviewChanges?.()
            })}
          >
            <Eye className="mr-2 h-4 w-4 text-blue-400" />
            <span>Preview Recommended Changes</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <TrendingUp className="mr-2 h-4 w-4 text-emerald-400" />
            <span>Apply Top Optimization</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              onStartABTest?.()
            })}
          >
            <FlaskConical className="mr-2 h-4 w-4 text-amber-400" />
            <span>Start A/B Test</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => {
              onCompareVersions?.()
            })}
          >
            <History className="mr-2 h-4 w-4 text-cyan-400" />
            <span>Compare Workflow Versions</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <RotateCcw className="mr-2 h-4 w-4 text-red-400" />
            <span>Roll Back Workflow</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <Activity className="mr-2 h-4 w-4 text-pink-400" />
            <span>View Agent Performance</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Workflow Commands */}
        <CommandGroup heading="Workflows">
          <CommandItem
            onSelect={() => runCommand(() => router.push("/workflows/new/builder"))}
          >
            <Plus className="mr-2 h-4 w-4" />
            <span>New Workflow</span>
            <CommandShortcut>N</CommandShortcut>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/workflows"))}
          >
            <Workflow className="mr-2 h-4 w-4" />
            <span>View All Workflows</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/workflows/failure-predictions"))}
          >
            <ShieldAlert className="mr-2 h-4 w-4 text-red-400" />
            <span>Workflow Failure Alerts</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <Shield className="mr-2 h-4 w-4 text-red-400" />
            <span>Add Approval Gate</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <GitBranch className="mr-2 h-4 w-4 text-violet-400" />
            <span>Add Decision Node</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => {})}>
            <Users className="mr-2 h-4 w-4 text-amber-400" />
            <span>Add Agent Council</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Navigation */}
        <CommandGroup heading="Navigate">
          <CommandItem
            onSelect={() => runCommand(() => router.push("/"))}
          >
            <Home className="mr-2 h-4 w-4" />
            <span>Dashboard</span>
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
            <span>Data Sources</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/deliverables"))}
          >
            <FileText className="mr-2 h-4 w-4" />
            <span>Deliverables</span>
          </CommandItem>
          <CommandItem
            onSelect={() => runCommand(() => router.push("/runs"))}
          >
            <Play className="mr-2 h-4 w-4" />
            <span>Runs</span>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* Quick Actions */}
        <CommandGroup heading="Actions">
          <CommandItem onSelect={() => runCommand(() => {})}>
            <Plug className="mr-2 h-4 w-4 text-amber-400" />
            <span>Add Missing Connector</span>
          </CommandItem>
          <CommandItem onSelect={() => runCommand(() => router.push("/deliverables"))}>
            <FileText className="mr-2 h-4 w-4 text-emerald-400" />
            <span>Open Goal Deliverables</span>
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
