"use client"

import { useCallback, useEffect, useState } from "react"
import { motion } from "framer-motion"
import { ADMIN_SIDEBAR_NAV } from "@/components/gravitre/sidebar-nav-config"
import { resolveSidebarNavIcon } from "@/components/gravitre/nodus-product/sidebar-nucleo"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { BeforeAfterPanel } from "./before-after-panel"

type NavMode = "compact" | "expanded" | "pinned" | "keyboard" | "mobile"

export function NavRailPrototype({ scene }: { scene: string }) {
  const mode: NavMode = scene.includes("mobile")
    ? "mobile"
    : scene.includes("pinned")
      ? "pinned"
      : scene.includes("expanded")
        ? "expanded"
        : scene.includes("keyboard")
          ? "keyboard"
          : "compact"

  const [expanded, setExpanded] = useState(mode === "expanded" || mode === "pinned")
  const [pinned, setPinned] = useState(mode === "pinned")
  const [mobileOpen, setMobileOpen] = useState(mode === "mobile")
  const [focusIndex, setFocusIndex] = useState(mode === "keyboard" ? 3 : -1)

  useEffect(() => {
    setExpanded(mode === "expanded" || mode === "pinned")
    setPinned(mode === "pinned")
    setMobileOpen(mode === "mobile")
    setFocusIndex(mode === "keyboard" ? 3 : -1)
  }, [mode])

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (mode !== "keyboard") return
      const items = ADMIN_SIDEBAR_NAV.flatMap((g) => g.items).filter((i) => i.name !== "Getting Started")
      if (e.key === "ArrowDown") {
        e.preventDefault()
        setFocusIndex((i) => Math.min(items.length - 1, i + 1))
      }
      if (e.key === "ArrowUp") {
        e.preventDefault()
        setFocusIndex((i) => Math.max(0, i - 1))
      }
    },
    [mode],
  )

  const railWidth = expanded || pinned ? 220 : 64
  const flatItems = ADMIN_SIDEBAR_NAV.flatMap((g) => g.items).filter((i) => i.name !== "Getting Started")

  return (
    <div data-review-surface="navigation" data-review-scene={scene} onKeyDown={onKeyDown} tabIndex={0}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <p className={cn(TYPE.eyebrow, "mr-2")}>Navigation B — expandable labeled rail</p>
        <Button
          type="button"
          size="sm"
          variant={expanded ? "secondary" : "outline"}
          onClick={() => setExpanded((v) => !v)}
        >
          Click to {expanded ? "collapse" : "expand"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant={pinned ? "secondary" : "outline"}
          onClick={() => {
            setPinned((v) => !v)
            if (!pinned) setExpanded(true)
          }}
        >
          {pinned ? "Pinned" : "Pin labels"}
        </Button>
        {mode === "mobile" ? (
          <Button type="button" size="sm" variant="outline" onClick={() => setMobileOpen((v) => !v)}>
            {mobileOpen ? "Close drawer" : "Open drawer"}
          </Button>
        ) : null}
      </div>

      <div
        className={cn(
          "relative flex overflow-hidden rounded-xl border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)]",
          mode === "mobile" ? "h-[640px] max-w-[390px]" : "h-[520px]",
        )}
      >
        {/* Simulated top bar — audited together with rail */}
        <div className="absolute inset-x-0 top-0 z-10 flex h-11 items-center justify-between border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-3">
          <span className={TYPE.meta}>Northwind · Production</span>
          <span className={TYPE.meta}>⌘K · Notifications · Profile</span>
        </div>

        {mode === "mobile" && mobileOpen ? (
          <div className="absolute inset-0 z-20 bg-black/20" onClick={() => setMobileOpen(false)} aria-hidden />
        ) : null}

        <motion.aside
          animate={{ width: mode === "mobile" ? (mobileOpen ? 220 : 0) : railWidth }}
          transition={{ type: "spring", stiffness: 280, damping: 28 }}
          className={cn(
            "relative z-30 mt-11 flex h-[calc(100%-2.75rem)] shrink-0 flex-col border-r border-[color:var(--g-border-subtle)] bg-[color:var(--g-background)] overflow-hidden",
            mode === "mobile" && !mobileOpen && "pointer-events-none",
          )}
        >
          <div className="flex h-10 items-center border-b border-[color:var(--g-border-subtle)] px-3">
            {expanded || pinned ? (
              <span className="text-sm font-semibold">Gravitre</span>
            ) : (
              <span className="mx-auto h-6 w-6 rounded bg-[color:var(--g-surface-2)]" />
            )}
          </div>
          <nav className="flex-1 overflow-y-auto py-2" aria-label="Primary">
            {ADMIN_SIDEBAR_NAV.map((group) => (
              <div key={group.group} className="mb-2">
                {expanded || pinned ? (
                  <p className={cn(TYPE.eyebrow, "px-3 py-1")}>{group.group}</p>
                ) : null}
                {group.items
                  .filter((item) => item.name !== "Getting Started")
                  .map((item) => {
                    const Icon = resolveSidebarNavIcon(item.icon)
                    const idx = flatItems.findIndex((f) => f.href === item.href)
                    const active = focusIndex === idx || item.name === "Activity"
                    return (
                      <a
                        key={item.href}
                        href={item.href}
                        onClick={(e) => e.preventDefault()}
                        className={cn(
                          "mx-1 flex items-center gap-2.5 rounded-lg py-2 text-sm transition-colors",
                          expanded || pinned ? "px-3" : "justify-center px-0",
                          active
                            ? "bg-[color:var(--g-emerald-soft)] text-[color:var(--g-emerald)]"
                            : "text-[color:var(--g-text-muted)] hover:bg-[color:var(--g-surface-2)]",
                          mode === "keyboard" && focusIndex === idx && "ring-2 ring-[color:var(--g-emerald)]",
                        )}
                        title={!expanded && !pinned ? item.name : undefined}
                      >
                        <Icon size={18} />
                        {expanded || pinned ? (
                          <span className="truncate font-medium">{item.name}</span>
                        ) : null}
                      </a>
                    )
                  })}
              </div>
            ))}
          </nav>
          {(expanded || pinned) && (
            <p className={cn(TYPE.meta, "border-t border-[color:var(--g-border-subtle)] px-3 py-2")}>
              {pinned ? "Labels pinned · click collapse in top bar" : "Click rail edge or control to expand · no hover-only"}
            </p>
          )}
        </motion.aside>

        <main className="mt-11 flex-1 p-4">
          <p className={TYPE.eyebrow}>Content canvas</p>
          <p className={cn(TYPE.sectionTitle, "mt-2")}>
            {mode === "compact" && "Icon-only rail — tooltips on hover, click to expand"}
            {mode === "expanded" && "Expanded labels — Linear-style alignment"}
            {mode === "pinned" && "Pinned expanded — persists across sessions"}
            {mode === "keyboard" && "Arrow ↑↓ moves focus · Enter activates"}
            {mode === "mobile" && "Drawer overlay · bottom nav for primary destinations"}
          </p>
          <p className={cn(TYPE.bodyMuted, "mt-2 max-w-md text-sm")}>
            Destinations unchanged from `sidebar-nav-config.ts`. Top bar stays coupled — workspace, env, command, notifications
            not redesigned independently.
          </p>
        </main>
      </div>

      <BeforeAfterPanel
        surface="navigation"
        changes={[
          { action: "removed", detail: "Tooltip-only wayfinding as sole label source" },
          { action: "contextual", detail: "Click-to-expand and pin — no disruptive hover expansion" },
          { action: "consolidated", detail: "Section labels appear only when rail expanded" },
          { action: "clearer", detail: "Same 14 destinations; deep links preserved" },
        ]}
      />
    </div>
  )
}
