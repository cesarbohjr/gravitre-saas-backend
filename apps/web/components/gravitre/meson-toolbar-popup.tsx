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
import { usePathname, useRouter } from "next/navigation"
import { AnimatePresence, motion } from "framer-motion"
import { Blocks, ChevronDown, X } from "lucide-react"
import { MesonPagePanel } from "@/components/gravitre/meson-page-panel"
import type { MesonSuggestion } from "@/lib/api"
import {
  resolveMesonPageFromPath,
  routeMesonSuggestion,
  shouldShowMesonToolbar,
} from "@/lib/meson-page-context"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

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

export function MesonToolbarProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const [mounted, setMounted] = useState(false)
  const [panelOpen, setPanelOpen] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (shouldShowMesonToolbar(pathname)) {
      setPanelOpen(true)
    } else {
      setPanelOpen(false)
    }
  }, [pathname])

  const visible = mounted && shouldShowMesonToolbar(pathname)

  const togglePanel = useCallback(() => {
    setPanelOpen((current) => !current)
  }, [])

  const closePanel = useCallback(() => {
    setPanelOpen(false)
  }, [])

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
              "relative h-8 w-8 rounded-full p-0 hover:bg-violet-500/10",
              panelOpen && "bg-violet-500/10 ring-1 ring-violet-500/30",
            )}
            aria-expanded={panelOpen}
            aria-label={panelOpen ? "Hide Meson tips" : "Show Meson tips"}
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-600 shadow-sm">
              <Blocks className="h-3.5 w-3.5 text-white" />
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
          <div className="max-h-[min(50vh,360px)] overflow-y-auto p-3">
            <MesonPagePanel
              key={`${mesonPage.page}:${mesonPage.entityId ?? ""}`}
              page={mesonPage.page}
              entityId={mesonPage.entityId}
              compact
              onSuggestionClick={handleSuggestionClick}
            />
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
}
