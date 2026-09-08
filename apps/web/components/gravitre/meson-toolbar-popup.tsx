"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import Link from "next/link"
import { usePathname, useRouter } from "next/navigation"
import useSWR from "swr"
import { AnimatePresence, motion } from "framer-motion"
import { Blocks, ChevronDown, Sparkles, X } from "lucide-react"
import { MesonPagePanel } from "@/components/gravitre/meson-page-panel"
import { NucleoAgent } from "@/components/icons/nucleo/semantic"
import { mesonApi, type MesonSuggestion } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  resolveMesonPageFromPath,
  routeMesonSuggestion,
  shouldShowMesonToolbar,
} from "@/lib/meson-page-context"
import { cn } from "@/lib/utils"
import { TOUCH_ICON_BUTTON } from "@/lib/design-system"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

/**
 * Quick-launch prompts into the full AI workspace, surfaced from the top Meson
 * box (replaces the retired bottom-right helper launcher — single entry point).
 */
const QUICK_LAUNCH_PROMPTS = [
  { label: "Summarize pending approvals", prompt: "Summarize my pending approvals and what needs a decision." },
  { label: "Agent status overview", prompt: "Give me a brief status of my agents and anything failing." },
  { label: "Recent run failures", prompt: "What workflow runs failed recently and why?" },
  { label: "Connector health", prompt: "Which connectors need attention right now?" },
] as const

/**
 * Meson as the voice of Gravitre: surfaces the org's real, org-wide GIBE
 * business-intelligence signal (same source as the /intelligence page),
 * independent of whatever page-specific tips are showing below it.
 */
function MesonGibeVoice() {
  const { user } = useAuth()
  const swrKey = user ? ["meson-gibe-voice"] : null
  const { data, isLoading } = useSWR(swrKey, () => mesonApi.insights(), {
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
    dedupingInterval: 120_000,
    keepPreviousData: true,
  })

  const insight = data?.insights?.find((item) => item.title?.trim() && item.summary?.trim())

  if (isLoading && !insight) {
    return (
      <div className="space-y-1.5 rounded-lg border border-violet-500/15 bg-violet-500/5 p-2.5">
        <Skeleton className="h-3 w-2/3 bg-violet-500/10" />
        <Skeleton className="h-3 w-full bg-violet-500/10" />
      </div>
    )
  }

  if (!insight) return null

  return (
    <div className="rounded-lg border border-violet-500/15 bg-violet-500/5 p-2.5">
      <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-400">
        <Sparkles className="h-3 w-3" />
        GIBE · Meson&apos;s take
      </div>
      <p className="text-xs font-medium leading-snug text-foreground">{insight.title}</p>
      <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-muted-foreground">
        {insight.summary}
      </p>
      <Link
        href={APP_ROUTES.intelligence}
        className="mt-1 inline-block text-[10px] font-medium text-violet-600 underline-offset-4 hover:underline dark:text-violet-400"
      >
        Advisory only — open Intelligence (GIBE)
      </Link>
    </div>
  )
}

/** The quick-launcher/setup option, folded into the top Meson box. */
function MesonQuickLauncher() {
  const router = useRouter()

  const openFull = (prompt?: string) => {
    const href = prompt
      ? `${APP_ROUTES.gravitreAi}?prompt=${encodeURIComponent(prompt)}`
      : APP_ROUTES.gravitreAi
    router.push(href)
  }

  return (
    <div className="mt-3 border-t border-border/60 pt-3">
      <p className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <NucleoAgent className="h-3 w-3" />
        Quick launcher
      </p>
      <ul className="space-y-1">
        {QUICK_LAUNCH_PROMPTS.map((item) => (
          <li key={item.label}>
            <button
              type="button"
              onClick={() => openFull(item.prompt)}
              className={cn(
                "w-full rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] px-2.5 py-2 text-left text-xs",
                "transition-colors hover:bg-[color:var(--g-surface-2)]",
              )}
            >
              {item.label}
            </button>
          </li>
        ))}
      </ul>
      <Button type="button" size="sm" className="mt-2 w-full" onClick={() => openFull()}>
        Open full AI workspace
      </Button>
    </div>
  )
}

type MesonToolbarContextValue = {
  visible: boolean
  panelOpen: boolean
  togglePanel: () => void
  closePanel: () => void
}

const MesonToolbarContext = createContext<MesonToolbarContextValue | null>(null)

function useMesonToolbar(): MesonToolbarContextValue {
  const value = useContext(MesonToolbarContext)
  if (!value) {
    throw new Error("useMesonToolbar must be used within MesonToolbarProvider")
  }
  return value
}

const MESON_PANEL_PREF_KEY = "gravitre:meson-panel-open"

export function MesonToolbarProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const [mounted, setMounted] = useState(false)
  // Default to closed so the panel never floats over content unprompted.
  // The user's explicit open/closed choice is remembered across navigation.
  const [panelOpen, setPanelOpen] = useState(false)

  useEffect(() => {
    setMounted(true)
    try {
      setPanelOpen(window.localStorage.getItem(MESON_PANEL_PREF_KEY) === "1")
    } catch {
      /* ignore storage access errors */
    }
  }, [])

  // When navigating to a surface that doesn't support Meson, hide the panel —
  // but never auto-open it on surfaces that do (that was the source of clutter).
  useEffect(() => {
    if (!shouldShowMesonToolbar(pathname)) {
      setPanelOpen(false)
    }
  }, [pathname])

  const persistPref = useCallback((open: boolean) => {
    try {
      window.localStorage.setItem(MESON_PANEL_PREF_KEY, open ? "1" : "0")
    } catch {
      /* ignore storage access errors */
    }
  }, [])

  const visible = mounted && shouldShowMesonToolbar(pathname)

  const togglePanel = useCallback(() => {
    setPanelOpen((current) => {
      const next = !current
      persistPref(next)
      return next
    })
  }, [persistPref])

  const closePanel = useCallback(() => {
    setPanelOpen(false)
    persistPref(false)
  }, [persistPref])

  const value = useMemo(
    () => ({
      visible,
      panelOpen,
      togglePanel,
      closePanel,
    }),
    [visible, panelOpen, togglePanel, closePanel],
  )

  return <MesonToolbarContext.Provider value={value}>{children}</MesonToolbarContext.Provider>
}

export function MesonToolbarTrigger() {
  const { visible, panelOpen, togglePanel } = useMesonToolbar()

  if (!visible) return null

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={togglePanel}
            className={cn(
              "relative rounded-full p-0 hover:bg-violet-500/10",
              TOUCH_ICON_BUTTON,
              panelOpen && "bg-violet-500/10 ring-1 ring-violet-500/30",
            )}
            aria-expanded={panelOpen}
            aria-label={panelOpen ? "Hide Meson tips" : "Show Meson tips"}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-600 shadow-sm sm:h-7 sm:w-7">
              <Blocks className="h-4 w-4 text-white sm:h-3.5 sm:w-3.5" />
            </span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="text-xs">
          Meson tips & insights
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export function MesonToolbarPopup() {
  const pathname = usePathname()
  const router = useRouter()
  const { visible, panelOpen, closePanel, togglePanel } = useMesonToolbar()
  const mesonPage = useMemo(() => resolveMesonPageFromPath(pathname), [pathname])

  const handleSuggestionClick = useCallback(
    (suggestion: MesonSuggestion) => {
      routeMesonSuggestion(pathname, suggestion, (href) => router.push(href))
    },
    [pathname, router],
  )

  if (!visible) return null

  return (
    <AnimatePresence initial={false}>
      {panelOpen ? (
        <motion.div
          key="meson-panel"
          initial={{ opacity: 0, y: -8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -6, scale: 0.98 }}
          transition={{ duration: 0.18 }}
          className="pointer-events-auto fixed right-3 top-[3.75rem] z-[70] w-[min(calc(100vw-1.5rem),22rem)] overflow-hidden rounded-2xl border border-violet-500/20 bg-card/95 shadow-xl shadow-violet-500/10 backdrop-blur-md sm:right-4"
        >
          <div className="flex items-center justify-between border-b border-border/60 px-3 py-2">
            <div className="flex items-center gap-2 text-xs font-medium text-foreground">
              <Blocks className="h-3.5 w-3.5 text-violet-500" />
              Meson tips
            </div>
            <div className="flex items-center gap-1">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label="Minimize Meson"
                onClick={togglePanel}
              >
                <ChevronDown className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                aria-label="Close Meson"
                onClick={closePanel}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <div className="max-h-[min(70vh,480px)] overflow-y-auto p-3">
            <MesonGibeVoice />
            <div className="mt-3">
              <MesonPagePanel
                key={`${mesonPage.page}:${mesonPage.entityId ?? ""}`}
                page={mesonPage.page}
                entityId={mesonPage.entityId}
                compact
                onSuggestionClick={handleSuggestionClick}
              />
            </div>
            <MesonQuickLauncher />
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
