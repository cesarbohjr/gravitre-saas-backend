"use client"

/**
 * Slice 0 Window Manager presentation controller.
 * Demonstrates contextual default + preference + mode transitions while
 * preserving identity references. Not a second chat runtime.
 */

import { useCallback, useMemo, useState, type ReactNode } from "react"
import { useWindowManagerPreference } from "@/hooks/use-window-manager-preference"
import { Button } from "@/components/ui/button"
import { GravitreDockedShell } from "@/components/gravitre/window-manager/gravitre-docked-shell"
import { GravitreWindowFrame } from "@/components/gravitre/window-manager/gravitre-window-frame"
import { ChatWindowControls } from "@/components/gravitre/chat-window-controls"
import { TYPE } from "@/lib/design-system"
import {
  resolveContextualWindowDefault,
  resolvePreferredWindowMode,
  transitionWindowMode,
  writeWindowManagerPreference,
  windowManagerModeToLegacy,
  type WindowManagerIdentity,
  type WindowManagerMode,
  type WindowManagerPreferenceMode,
  WINDOW_MANAGER_MODES,
} from "@/lib/gravitre-window-manager"
import { surfaceForPresentationMode } from "@/lib/chat-window-state"
import { cn } from "@/lib/utils"

const DEMO_IDENTITY: WindowManagerIdentity = {
  conversationId: "conv_slice0_demo_001",
  taskId: "task_qualify_acme",
  artifactId: "art_contact_draft",
  approvalId: "appr_outreach_1",
  voiceSessionId: null,
}

export function GravitreWindowManagerShell({
  pathname = "/dashboard",
  viewportWidth = 1280,
  pageContextSlot,
  children,
}: {
  pathname?: string
  viewportWidth?: number
  pageContextSlot?: ReactNode
  children?: ReactNode
}) {
  const contextual = useMemo(
    () =>
      resolveContextualWindowDefault({
        pathname,
        viewportWidth,
        expertWorkspace: pathname.includes("/workflows/"),
      }),
    [pathname, viewportWidth],
  )

  // Server + hydrating render: preference is null → contextual default. The stored
  // preference arrives in the post-hydration render via useSyncExternalStore.
  const preference = useWindowManagerPreference()
  const resolved = resolvePreferredWindowMode({
    hints: { pathname, viewportWidth, expertWorkspace: pathname.includes("/workflows/") },
    preference,
  })
  const [explicit, setExplicit] = useState<{
    mode: Exclude<WindowManagerMode, "restored">
    lastMeaningful: WindowManagerPreferenceMode
  } | null>(null)
  const mode = explicit?.mode ?? resolved
  const lastMeaningful = explicit?.lastMeaningful ?? resolved
  const [identity] = useState(() => DEMO_IDENTITY)
  const [log, setLog] = useState<string[]>([])

  const applyMode = useCallback(
    (to: WindowManagerMode) => {
      const next = transitionWindowMode({ from: mode, to, identity, lastMeaningful })
      const nextMode = next.mode as Exclude<WindowManagerMode, "restored">
      setExplicit({ mode: nextMode, lastMeaningful: next.lastMeaningful })
      if (nextMode !== "minimized") writeWindowManagerPreference(next.lastMeaningful)
      setLog((rows) => [`${mode}→${nextMode} · ${identity.conversationId} unchanged`, ...rows].slice(0, 6))
    },
    [identity, lastMeaningful, mode],
  )

  const surface = surfaceForPresentationMode(
    windowManagerModeToLegacy(mode === "minimized" ? "compact" : mode),
  )
  const handlers = {
    expand: () => applyMode("expanded"),
    collapseToFloat: () => applyMode("floating"),
    fullscreen: () => applyMode("fullscreen"),
    exitFullscreen: () => applyMode(lastMeaningful),
    minimizeToHelper: () => applyMode("minimized"),
    openAsFloat: () => applyMode("floating"),
    dock: () => applyMode("docked"),
    undock: () => applyMode("floating"),
  }

  const body =
    children ??
    (
      <div className="space-y-2 p-3 text-sm">
        <p className={TYPE.body}>Conversation + task body (presentation stub — core runtime untouched).</p>
        <p className={TYPE.meta}>Approval: {identity.approvalId}</p>
        <p className={TYPE.meta}>Artifact: {identity.artifactId}</p>
      </div>
    )

  return (
    <div data-slice0-wm-shell="" data-wm-mode-source={explicit ? "explicit" : preference ? "preference" : "contextual"} className="space-y-3">
      <div className="flex flex-wrap gap-1" role="toolbar" aria-label="Window modes">
        {WINDOW_MANAGER_MODES.map((m) => (
          <Button
            key={m}
            type="button"
            size="sm"
            variant={mode === m ? "secondary" : "ghost"}
            aria-pressed={mode === m}
            onClick={() => applyMode(m)}
          >
            {m}
          </Button>
        ))}
      </div>
      <p className={TYPE.meta}>
        Contextual default: <strong>{contextual}</strong>
        {preference ? (
          <>
            {" "}
            · preference: <strong>{preference}</strong>
          </>
        ) : null}{" "}
        · active: <strong>{mode}</strong>
      </p>

      {mode === "minimized" ? (
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-full border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 py-2 text-xs"
          onClick={() => applyMode("restored")}
          aria-label="Restore window"
        >
          <span className="font-medium">Task · {identity.taskId}</span>
          <span className="text-[color:var(--g-text-muted)]">restore</span>
        </button>
      ) : mode === "docked" ? (
        <GravitreDockedShell identity={identity} handlers={handlers} pageContextSlot={pageContextSlot}>
          {body}
        </GravitreDockedShell>
      ) : (
        <GravitreWindowFrame
          mode={mode}
          identity={identity}
          role={mode === "fullscreen" ? "dialog" : "region"}
          className={cn(
            mode === "compact" && "h-[420px] w-[var(--g-wm-compact-width)]",
            mode === "floating" && "h-[480px] min-w-[var(--g-wm-floating-min-width)] w-[560px]",
            mode === "expanded" && "h-[560px] w-full max-w-5xl",
            mode === "fullscreen" && "h-[min(80vh,720px)] w-full",
          )}
          controls={<ChatWindowControls surface={surface} handlers={handlers} />}
        >
          {body}
        </GravitreWindowFrame>
      )}

      <ol className="font-mono text-[10px] text-[color:var(--g-text-muted)]">
        {log.map((row, i) => (
          <li key={`${i}-${row}`}>{row}</li>
        ))}
      </ol>
    </div>
  )
}
