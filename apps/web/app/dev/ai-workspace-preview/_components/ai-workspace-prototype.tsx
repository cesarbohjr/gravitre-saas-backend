"use client"

/**
 * PHASE 0 PROTOTYPE — isolated, unlinked, mock-data only.
 *
 * Implements the four presentation states from the "Gravitre AI Agent
 * Workspace" spec (Helper / Float / Expanded / Fullscreen) as real,
 * interactive React components, per docs/delivery/
 * ai-agent-floating-workspace-architecture-2026-09-07.md Part C3.
 *
 * NOT wired to real conversation state, real tools, or the real voice
 * pipeline. Nothing here is reachable from production nav. Do not import
 * this into app-shell.tsx or any real route without an explicit decision —
 * this is a review artifact, not a shipped surface.
 *
 * Tokens: reuses apps/web/app/globals.css / lib/design-system.ts verbatim
 * (no new tokens invented). Icons: Nucleo where it already exists, Lucide
 * fallback for the confirmed gaps (Expand/Minimize/Fullscreen/Drag-handle —
 * see architecture doc C1) — an explicitly accepted prototype-stage decision.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion, useDragControls } from "framer-motion"
import {
  Expand,
  Maximize2,
  Minimize2,
  GripVertical,
  Paperclip,
  Send,
  Sparkles,
} from "lucide-react"
import {
  NucleoAgent,
  NucleoApproval,
  NucleoClose,
  NucleoVoice,
} from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { TYPE } from "@/lib/design-system"

// ---------------------------------------------------------------------------
// Mock domain model — intentionally fake, never touches real API/tool state.
// ---------------------------------------------------------------------------

export type PresenceState =
  | "ready"
  | "listening"
  | "thinking"
  | "working"
  | "executing"
  | "needs_approval"
  | "complete"
  | "error"

export type WorkspaceMode = "helper" | "float" | "expanded" | "fullscreen"

type MockMessage = {
  id: string
  role: "user" | "assistant" | "tool" | "approval"
  content: string
  toolName?: string
  timestamp: string
}

const MOCK_MESSAGES: MockMessage[] = [
  {
    id: "m1",
    role: "user",
    content: "Which connectors need attention right now?",
    timestamp: "9:41 AM",
  },
  {
    id: "m2",
    role: "assistant",
    content: "Checking connector health across your org — one moment.",
    timestamp: "9:41 AM",
  },
  {
    id: "m3",
    role: "tool",
    toolName: "connectors.list_health",
    content: "Queried 6 connectors · 1 degraded (HubSpot), 5 healthy.",
    timestamp: "9:41 AM",
  },
  {
    id: "m4",
    role: "assistant",
    content:
      "HubSpot's token expires in 2 days — the rest are healthy. Want me to open the reconnect flow?",
    timestamp: "9:41 AM",
  },
  {
    id: "m5",
    role: "approval",
    toolName: "connectors.reconnect",
    content: "Approve reconnecting HubSpot using the stored OAuth client?",
    timestamp: "9:42 AM",
  },
]

const MOCK_THREADS = [
  { id: "t1", title: "Connector health check", active: true, updated: "2m ago" },
  { id: "t2", title: "Q3 pipeline summary", active: false, updated: "1h ago" },
  { id: "t3", title: "Agent failure triage", active: false, updated: "Yesterday" },
  { id: "t4", title: "Workflow: onboarding v2", active: false, updated: "2d ago" },
]

const PRESENCE_COPY: Record<PresenceState, { label: string; tone: string }> = {
  ready: { label: "Ready", tone: "text-[color:var(--g-text-muted)]" },
  listening: { label: "Listening", tone: "text-[color:var(--g-signal)]" },
  thinking: { label: "Thinking", tone: "text-[color:var(--g-intelligence)]" },
  working: { label: "Working", tone: "text-[color:var(--g-intelligence)]" },
  executing: { label: "Executing", tone: "text-[color:var(--g-signal)]" },
  needs_approval: { label: "Needs approval", tone: "text-[color:var(--g-approval)]" },
  complete: { label: "Complete", tone: "text-[color:var(--g-brand)]" },
  error: { label: "Error", tone: "text-[color:var(--g-danger)]" },
}

const PRESENCE_DOT: Record<PresenceState, string> = {
  ready: "bg-[color:var(--g-text-muted)]",
  listening: "bg-[color:var(--g-signal)]",
  thinking: "bg-[color:var(--g-intelligence)]",
  working: "bg-[color:var(--g-intelligence)]",
  executing: "bg-[color:var(--g-signal)]",
  needs_approval: "bg-[color:var(--g-approval)]",
  complete: "bg-[color:var(--g-brand)]",
  error: "bg-[color:var(--g-danger)]",
}

// ---------------------------------------------------------------------------
// Shared window geometry
// ---------------------------------------------------------------------------

const FLOAT_DEFAULT = { width: 520, height: 560 }
const FLOAT_MIN = { width: 400, height: 420 }

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

// ---------------------------------------------------------------------------
// STATE 1 — Helper (bottom-left persistent presence)
// ---------------------------------------------------------------------------

function GravitreAIHelper({
  presence,
  onOpen,
}: {
  presence: PresenceState
  onOpen: () => void
}) {
  const copy = PRESENCE_COPY[presence]
  return (
    <motion.button
      type="button"
      layoutId="gravitre-ai-window"
      onClick={onOpen}
      initial={false}
      className={cn(
        "fixed bottom-5 left-5 z-[85] flex items-center gap-2.5 rounded-full border border-divide",
        "bg-[color:var(--g-surface-1)] px-3 py-2 shadow-[var(--np-shadow)] transition-colors",
        "hover:bg-[color:var(--g-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]/40",
      )}
      aria-label={`Open Gravitre AI — ${copy.label}`}
    >
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[color:var(--g-brand)] to-emerald-700 text-white">
        <NucleoAgent className="h-4 w-4" />
        <span
          className={cn(
            "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-[color:var(--g-surface-1)]",
            PRESENCE_DOT[presence],
            (presence === "thinking" || presence === "working" || presence === "executing") &&
              "animate-pulse",
          )}
          aria-hidden
        />
      </span>
      <span className="hidden flex-col items-start pr-1 sm:flex">
        <span className="text-xs font-semibold text-[color:var(--g-text-primary)]">Gravitre AI</span>
        <span className={cn("text-[11px] font-medium", copy.tone)}>{copy.label}</span>
      </span>
    </motion.button>
  )
}

// ---------------------------------------------------------------------------
// Window chrome shared by Float / Expanded / Fullscreen
// ---------------------------------------------------------------------------

function WindowHeader({
  presence,
  onDragPointerDown,
  onMinimize,
  onExpand,
  onFullscreen,
  onClose,
  mode,
}: {
  presence: PresenceState
  onDragPointerDown?: (event: React.PointerEvent) => void
  onMinimize: () => void
  onExpand?: () => void
  onFullscreen?: () => void
  onClose: () => void
  mode: WorkspaceMode
}) {
  const copy = PRESENCE_COPY[presence]
  return (
    <div
      onPointerDown={onDragPointerDown}
      className={cn(
        "flex items-center justify-between border-b border-divide px-3 py-2.5",
        mode === "float" && "cursor-grab select-none active:cursor-grabbing",
      )}
      data-window-drag-handle=""
    >
      <div className="flex min-w-0 items-center gap-2">
        <GripVertical
          className={cn("h-3.5 w-3.5 text-[color:var(--g-text-muted)]", mode !== "float" && "opacity-0")}
          aria-hidden
        />
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--np-radius-sm)] bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]">
          <NucleoAgent className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-[color:var(--g-text-primary)]">Gravitre AI</p>
        </div>
        <span
          className={cn(
            "ml-1 flex items-center gap-1 rounded-full bg-[color:var(--g-surface-2)] px-1.5 py-0.5 text-[10px] font-medium",
            copy.tone,
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", PRESENCE_DOT[presence])} aria-hidden />
          {copy.label}
        </span>
      </div>
      <div className="flex items-center gap-0.5">
        <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label="Minimize" onClick={onMinimize}>
          <Minimize2 className="h-3.5 w-3.5" />
        </Button>
        {onExpand ? (
          <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label="Expand" onClick={onExpand}>
            <Maximize2 className="h-3.5 w-3.5" />
          </Button>
        ) : null}
        {onFullscreen ? (
          <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label="Fullscreen" onClick={onFullscreen}>
            <Expand className="h-3.5 w-3.5" />
          </Button>
        ) : null}
        <Button type="button" variant="ghost" size="icon" className="h-7 w-7" aria-label="Close to helper" onClick={onClose}>
          <NucleoClose className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: MockMessage }) {
  if (message.role === "tool") {
    return (
      <div className="my-1.5 flex items-center gap-2 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] px-2.5 py-1.5 text-[11px] text-[color:var(--g-text-muted)]">
        <Sparkles className="h-3 w-3 shrink-0 text-[color:var(--g-signal)]" aria-hidden />
        <span className="truncate">
          <span className="font-medium text-[color:var(--g-text-primary)]">{message.toolName}</span>
          {" · "}
          {message.content}
        </span>
      </div>
    )
  }
  if (message.role === "approval") {
    return (
      <div className="my-1.5 rounded-[var(--np-radius-md)] border border-[color:var(--g-approval)]/30 bg-[color:var(--g-approval-surface)] p-2.5">
        <div className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold text-[color:var(--g-approval)]">
          <NucleoApproval className="h-3.5 w-3.5" />
          Needs your approval
        </div>
        <p className="text-xs text-[color:var(--g-text-primary)]">{message.content}</p>
        <div className="mt-2 flex gap-1.5">
          <Button type="button" size="sm" className="h-7 flex-1 text-xs">
            Approve
          </Button>
          <Button type="button" size="sm" variant="outline" className="h-7 flex-1 text-xs">
            Deny
          </Button>
        </div>
      </div>
    )
  }
  const isUser = message.role === "user"
  return (
    <div className={cn("my-1 flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-[var(--np-radius-lg)] px-3 py-2 text-xs leading-relaxed",
          isUser
            ? "bg-[color:var(--g-brand)] text-white"
            : "border border-divide bg-[color:var(--g-surface-1)] text-[color:var(--g-text-primary)]",
        )}
      >
        {message.content}
      </div>
    </div>
  )
}

function ConversationView({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn("flex-1 overflow-y-auto px-3 py-3", compact && "px-2.5 py-2.5")}>
      {MOCK_MESSAGES.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  )
}

function Composer({ presence }: { presence: PresenceState }) {
  return (
    <div className="border-t border-divide p-2.5">
      <div className="flex items-end gap-1.5 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-1.5">
        <Button type="button" variant="ghost" size="icon" className="h-8 w-8 shrink-0" aria-label="Attach file">
          <Paperclip className="h-3.5 w-3.5" />
        </Button>
        <input
          type="text"
          placeholder="Ask Gravitre AI…"
          className="flex-1 bg-transparent text-xs text-[color:var(--g-text-primary)] outline-none placeholder:text-[color:var(--g-text-muted)]"
          readOnly
        />
        <Button
          type="button"
          variant={presence === "listening" ? "default" : "ghost"}
          size="icon"
          className="h-8 w-8 shrink-0"
          aria-label="Voice input"
        >
          <NucleoVoice className="h-3.5 w-3.5" />
        </Button>
        <Button type="button" size="icon" className="h-8 w-8 shrink-0" aria-label="Send">
          <Send className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// STATE 2 — Floating workspace (draggable + resizable)
// ---------------------------------------------------------------------------

function GravitreFloatingWorkspace({
  presence,
  onMinimize,
  onExpand,
  onFullscreen,
  onClose,
}: {
  presence: PresenceState
  onMinimize: () => void
  onExpand: () => void
  onFullscreen: () => void
  onClose: () => void
}) {
  const [size, setSize] = useState(FLOAT_DEFAULT)
  const [viewport, setViewport] = useState({ width: 1280, height: 800 })
  const containerRef = useRef<HTMLDivElement | null>(null)
  const resizeStart = useRef<{ x: number; y: number; w: number; h: number } | null>(null)
  const dragControls = useDragControls()

  useEffect(() => {
    const update = () => setViewport({ width: window.innerWidth, height: window.innerHeight })
    update()
    window.addEventListener("resize", update)
    return () => window.removeEventListener("resize", update)
  }, [])

  const onResizePointerDown = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      resizeStart.current = { x: event.clientX, y: event.clientY, w: size.width, h: size.height }
      const onMove = (moveEvent: PointerEvent) => {
        if (!resizeStart.current) return
        const dx = moveEvent.clientX - resizeStart.current.x
        const dy = moveEvent.clientY - resizeStart.current.y
        setSize({
          width: clamp(resizeStart.current.w + dx, FLOAT_MIN.width, 900),
          height: clamp(resizeStart.current.h + dy, FLOAT_MIN.height, 800),
        })
      }
      const onUp = () => {
        resizeStart.current = null
        window.removeEventListener("pointermove", onMove)
        window.removeEventListener("pointerup", onUp)
      }
      window.addEventListener("pointermove", onMove)
      window.addEventListener("pointerup", onUp)
    },
    [size.height, size.width],
  )

  return (
    <motion.div
      layoutId="gravitre-ai-window"
      drag
      dragListener={false}
      dragControls={dragControls}
      dragMomentum={false}
      dragElastic={0}
      dragConstraints={{
        left: 8,
        right: Math.max(8, viewport.width - size.width - 8),
        top: 8,
        bottom: Math.max(8, viewport.height - size.height - 8),
      }}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-auto fixed bottom-5 left-5 z-[85] flex flex-col overflow-hidden rounded-[var(--g-radius-panel)] border border-divide bg-[color:var(--g-surface-1)] shadow-2xl"
      style={{ width: size.width, height: size.height }}
      ref={containerRef}
    >
      <FloatDragHeader
        presence={presence}
        onDragPointerDown={(event) => {
          // Never start a drag from an interactive control inside the header
          // (spec item 22 — drag must not swallow button clicks).
          const target = event.target as HTMLElement
          if (target.closest("button,a,input,textarea")) return
          dragControls.start(event)
        }}
        onMinimize={onMinimize}
        onExpand={onExpand}
        onFullscreen={onFullscreen}
        onClose={onClose}
      />
      <ConversationView compact />
      <Composer presence={presence} />
      <div
        role="separator"
        aria-label="Resize window"
        onPointerDown={onResizePointerDown}
        className="absolute bottom-0.5 right-0.5 flex h-4 w-4 cursor-nwse-resize items-center justify-center text-[color:var(--g-text-muted)]/50 hover:text-[color:var(--g-text-muted)]"
      >
        <GripVertical className="h-3 w-3 rotate-45" />
      </div>
    </motion.div>
  )
}

/** Header scoped to Float mode — the only region that starts a drag (dragControls.start). */
function FloatDragHeader({
  presence,
  onDragPointerDown,
  onMinimize,
  onExpand,
  onFullscreen,
  onClose,
}: {
  presence: PresenceState
  onDragPointerDown: (event: React.PointerEvent) => void
  onMinimize: () => void
  onExpand: () => void
  onFullscreen: () => void
  onClose: () => void
}) {
  return (
    <WindowHeader
      presence={presence}
      mode="float"
      onDragPointerDown={onDragPointerDown}
      onMinimize={onMinimize}
      onExpand={onExpand}
      onFullscreen={onFullscreen}
      onClose={onClose}
    />
  )
}

// ---------------------------------------------------------------------------
// STATE 3 / 4 — Expanded (3-panel) and Fullscreen share a shell
// ---------------------------------------------------------------------------

function LeftPanel() {
  return (
    <div className="flex w-56 flex-col border-r border-divide bg-[color:var(--g-surface-2)]/40">
      <div className="border-b border-divide px-3 py-2.5">
        <p className={TYPE.eyebrow}>Threads</p>
      </div>
      <ul className="flex-1 overflow-y-auto p-2">
        {MOCK_THREADS.map((thread) => (
          <li key={thread.id}>
            <button
              type="button"
              className={cn(
                "w-full rounded-[var(--np-radius-md)] px-2.5 py-2 text-left text-xs transition-colors",
                thread.active
                  ? "bg-[color:var(--g-brand-soft)] font-medium text-[color:var(--g-brand)]"
                  : "text-[color:var(--g-text-primary)] hover:bg-[color:var(--g-surface-2)]",
              )}
            >
              <span className="block truncate">{thread.title}</span>
              <span className="block text-[10px] text-[color:var(--g-text-muted)]">{thread.updated}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RightPanel({ presence, pageContext }: { presence: PresenceState; pageContext: string }) {
  return (
    <div className="flex w-64 flex-col border-l border-divide bg-[color:var(--g-surface-2)]/40">
      <div className="border-b border-divide px-3 py-2.5">
        <p className={TYPE.eyebrow}>Context</p>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--g-text-muted)]">
            Current page
          </p>
          <p className="mt-1 text-xs font-medium text-[color:var(--g-text-primary)]">{pageContext}</p>
        </div>
        {presence === "needs_approval" ? (
          <div className="rounded-[var(--np-radius-md)] border border-[color:var(--g-approval)]/30 bg-[color:var(--g-approval-surface)] p-2.5">
            <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-[color:var(--g-approval)]">
              <NucleoApproval className="h-3 w-3" />
              Pending approval
            </p>
            <p className="mt-1 text-xs text-[color:var(--g-text-primary)]">connectors.reconnect</p>
          </div>
        ) : null}
        <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[color:var(--g-text-muted)]">
            Evidence
          </p>
          <p className="mt-1 text-xs text-[color:var(--g-text-primary)]">connectors.list_health · 6 checked</p>
        </div>
      </div>
    </div>
  )
}

function GravitreAIWorkspaceShell({
  mode,
  presence,
  pageContext,
  onMinimize,
  onCollapseToFloat,
  onFullscreen,
  onExpand,
  onClose,
}: {
  mode: "expanded" | "fullscreen"
  presence: PresenceState
  pageContext: string
  onMinimize: () => void
  onCollapseToFloat: () => void
  onFullscreen: () => void
  onExpand: () => void
  onClose: () => void
}) {
  const isFullscreen = mode === "fullscreen"
  return (
    <motion.div
      layoutId="gravitre-ai-window"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "pointer-events-auto fixed z-[85] flex flex-col overflow-hidden border border-divide bg-[color:var(--g-surface-1)] shadow-2xl",
        isFullscreen
          ? "inset-0 rounded-none"
          : "inset-6 rounded-[var(--g-radius-panel)] sm:inset-10 md:inset-x-16 md:inset-y-10",
      )}
    >
      <WindowHeader
        presence={presence}
        mode={mode}
        onMinimize={onMinimize}
        onExpand={undefined}
        onFullscreen={isFullscreen ? undefined : onFullscreen}
        onClose={onClose}
      />
      {!isFullscreen ? (
        <div className="flex justify-end border-b border-divide px-2 py-1">
          <Button type="button" variant="ghost" size="sm" className="h-6 gap-1 text-[11px]" onClick={onCollapseToFloat}>
            <Minimize2 className="h-3 w-3" /> Collapse to float
          </Button>
        </div>
      ) : (
        <div className="flex justify-end border-b border-divide px-2 py-1">
          <Button type="button" variant="ghost" size="sm" className="h-6 gap-1 text-[11px]" onClick={onExpand}>
            <Minimize2 className="h-3 w-3" /> Exit fullscreen
          </Button>
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <LeftPanel />
        <div className="flex flex-1 flex-col">
          <ConversationView />
          <Composer presence={presence} />
        </div>
        <RightPanel presence={presence} pageContext={pageContext} />
      </div>
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Mobile sheet (bottom sheet pattern instead of a draggable float)
// ---------------------------------------------------------------------------

function GravitreAIMobileSheet({
  presence,
  expanded,
  onToggleExpand,
  onClose,
}: {
  presence: PresenceState
  expanded: boolean
  onToggleExpand: () => void
  onClose: () => void
}) {
  return (
    <motion.div
      layoutId="gravitre-ai-window"
      initial={{ y: "100%" }}
      animate={{ y: 0 }}
      exit={{ y: "100%" }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "pointer-events-auto fixed inset-x-0 bottom-0 z-[85] flex flex-col overflow-hidden rounded-t-[var(--g-radius-panel)] border border-divide bg-[color:var(--g-surface-1)] shadow-2xl",
        expanded ? "top-0 rounded-t-none" : "h-[70vh]",
      )}
    >
      <div className="flex justify-center py-1.5" onClick={onToggleExpand} role="presentation">
        <span className="h-1 w-10 rounded-full bg-[color:var(--g-surface-2)]" />
      </div>
      <WindowHeader presence={presence} mode="expanded" onMinimize={onClose} onExpand={onToggleExpand} onFullscreen={undefined} onClose={onClose} />
      <ConversationView />
      <Composer presence={presence} />
    </motion.div>
  )
}

// ---------------------------------------------------------------------------
// Root prototype orchestrator
// ---------------------------------------------------------------------------

export function AiWorkspacePrototype() {
  const [mode, setMode] = useState<WorkspaceMode>("helper")
  const [presence, setPresence] = useState<PresenceState>("ready")
  const [isMobileViewport, setIsMobileViewport] = useState(false)
  const [pageContext, setPageContext] = useState("Dashboard")

  useEffect(() => {
    const check = () => setIsMobileViewport(window.innerWidth < 640)
    check()
    window.addEventListener("resize", check)
    return () => window.removeEventListener("resize", check)
  }, [])

  const transitions = useMemo(
    () => ({
      openFloat: () => setMode("float"),
      minimize: () => setMode("helper"),
      expand: () => setMode("expanded"),
      fullscreen: () => setMode("fullscreen"),
      collapseToFloat: () => setMode("float"),
      close: () => setMode("helper"),
    }),
    [],
  )

  return (
    <div className="relative">
      {/* Fake underlying app surface — proves Float doesn't block interaction (spec item 50) */}
      <MockUnderlyingApp pageContext={pageContext} onPageContextChange={setPageContext} />

      <DemoControls presence={presence} onPresenceChange={setPresence} mode={mode} onModeChange={setMode} />

      <AnimatePresence mode="popLayout">
        {mode === "helper" ? (
          <GravitreAIHelper key="helper" presence={presence} onOpen={transitions.openFloat} />
        ) : null}
        {mode === "float" && !isMobileViewport ? (
          <GravitreFloatingWorkspace
            key="float"
            presence={presence}
            onMinimize={transitions.minimize}
            onExpand={transitions.expand}
            onFullscreen={transitions.fullscreen}
            onClose={transitions.close}
          />
        ) : null}
        {mode === "float" && isMobileViewport ? (
          <GravitreAIMobileSheet
            key="mobile-sheet"
            presence={presence}
            expanded={false}
            onToggleExpand={transitions.expand}
            onClose={transitions.close}
          />
        ) : null}
        {mode === "expanded" && isMobileViewport ? (
          <GravitreAIMobileSheet
            key="mobile-sheet-expanded"
            presence={presence}
            expanded
            onToggleExpand={transitions.collapseToFloat}
            onClose={transitions.close}
          />
        ) : null}
        {(mode === "expanded" || mode === "fullscreen") && !isMobileViewport ? (
          <GravitreAIWorkspaceShell
            key="shell"
            mode={mode}
            presence={presence}
            pageContext={pageContext}
            onMinimize={transitions.minimize}
            onCollapseToFloat={transitions.collapseToFloat}
            onFullscreen={transitions.fullscreen}
            onExpand={transitions.expand}
            onClose={transitions.close}
          />
        ) : null}
      </AnimatePresence>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Fake underlying app + demo controls (prototype-only scaffolding)
// ---------------------------------------------------------------------------

function MockUnderlyingApp({
  pageContext,
  onPageContextChange,
}: {
  pageContext: string
  onPageContextChange: (value: string) => void
}) {
  const pages = ["Dashboard", "Agents", "Workflows", "Connectors", "GIBE"]
  return (
    <div className="min-h-screen bg-[color:var(--g-surface-3)] p-6 pl-6 sm:pl-8">
      <div className="mx-auto max-w-5xl">
        <p className={TYPE.eyebrow}>Mock Gravitre app (interaction proof only)</p>
        <h1 className={cn(TYPE.pageTitle, "mt-1")}>{pageContext}</h1>
        <p className={cn(TYPE.pageLead, "mt-1 max-w-xl")}>
          This is a fake underlying surface, not the real app. Click the page chips or the button below while
          the AI window is open (Float/Expanded) to confirm the workspace never blocks interaction.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {pages.map((page) => (
            <button
              key={page}
              type="button"
              onClick={() => onPageContextChange(page)}
              className={cn(
                "rounded-full border border-divide px-3 py-1.5 text-xs font-medium transition-colors",
                pageContext === page
                  ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand)]"
                  : "bg-[color:var(--g-surface-1)] text-[color:var(--g-text-primary)] hover:bg-[color:var(--g-surface-2)]",
              )}
            >
              {page}
            </button>
          ))}
        </div>
        <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[1, 2, 3].map((card) => (
            <div key={card} className="rounded-[var(--g-radius-panel)] border border-divide bg-[color:var(--g-surface-1)] p-4 shadow-[var(--np-shadow)]">
              <p className={TYPE.cardTitle}>Mock card {card}</p>
              <p className={cn(TYPE.meta, "mt-1")}>Clickable underlying content — confirms no blocking overlay.</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function DemoControls({
  presence,
  onPresenceChange,
  mode,
  onModeChange,
}: {
  presence: PresenceState
  onPresenceChange: (value: PresenceState) => void
  mode: WorkspaceMode
  onModeChange: (value: WorkspaceMode) => void
}) {
  const presences: PresenceState[] = ["ready", "listening", "thinking", "working", "executing", "needs_approval", "complete", "error"]
  const modes: WorkspaceMode[] = ["helper", "float", "expanded", "fullscreen"]
  return (
    <div className="fixed right-3 top-3 z-[90] w-72 rounded-[var(--g-radius-panel)] border border-divide bg-[color:var(--g-surface-1)]/95 p-3 shadow-[var(--np-shadow)] backdrop-blur-sm">
      <p className={TYPE.eyebrow}>Phase 0 demo controls</p>
      <p className={cn(TYPE.meta, "mt-1")}>Not part of the real product — review harness only.</p>
      <div className="mt-2">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[color:var(--g-text-muted)]">
          Mode
        </p>
        <div className="flex flex-wrap gap-1">
          {modes.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onModeChange(m)}
              className={cn(
                "rounded-full border border-divide px-2 py-1 text-[10px] font-medium capitalize transition-colors",
                mode === m ? "bg-[color:var(--g-brand)] text-white" : "bg-[color:var(--g-surface-2)]",
              )}
            >
              {m}
            </button>
          ))}
        </div>
      </div>
      <div className="mt-2">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-[color:var(--g-text-muted)]">
          Presence state
        </p>
        <div className="flex flex-wrap gap-1">
          {presences.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => onPresenceChange(p)}
              className={cn(
                "rounded-full border border-divide px-2 py-1 text-[10px] font-medium capitalize transition-colors",
                presence === p ? "bg-[color:var(--g-brand)] text-white" : "bg-[color:var(--g-surface-2)]",
              )}
            >
              {PRESENCE_COPY[p].label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
