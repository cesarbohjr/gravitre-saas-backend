"use client"

/**
 * Persistent app shell plumbing.
 *
 * The signed-in chrome (sidebar, top bar, banners, command palette and their
 * SWR fetches) is mounted once by `app/(app)/layout.tsx` through
 * `PersistentAppShell`, so it survives client navigation instead of
 * remounting with every page. Pages still describe the chrome they want —
 * title, breadcrumb vendor, full-viewport mode — by rendering
 * `<AppShell title=…>` (or calling `useAppShellOptions`). Under the persistent
 * host that only registers options here; it never renders a second shell.
 */

import { createContext, useCallback, useContext, useId, useLayoutEffect, useMemo, useState } from "react"

export interface AppShellOptions {
  title?: string
  /** Vendor key shown beside connector detail breadcrumbs. */
  breadcrumbVendor?: string
  /** Immersive, non-scrolling main region; the page owns its own scroll panes. */
  fillViewport?: boolean
}

interface AppShellHost {
  register: (id: string, options: AppShellOptions) => void
  unregister: (id: string) => void
}

const AppShellHostContext = createContext<AppShellHost | null>(null)

interface Registration {
  id: string
  options: AppShellOptions
}

function sameOptions(a: AppShellOptions, b: AppShellOptions): boolean {
  return a.title === b.title && a.breadcrumbVendor === b.breadcrumbVendor && a.fillViewport === b.fillViewport
}

/**
 * Owns the options registry. The most recently registered entry wins; updates
 * to an existing entry (e.g. a title that resolves after data loads) are made
 * in place so they don't reorder the stack.
 */
export function useAppShellHost(): { host: AppShellHost; options: AppShellOptions } {
  const [registrations, setRegistrations] = useState<Registration[]>([])

  const register = useCallback((id: string, options: AppShellOptions) => {
    setRegistrations((prev) => {
      const index = prev.findIndex((entry) => entry.id === id)
      if (index === -1) return [...prev, { id, options }]
      if (sameOptions(prev[index].options, options)) return prev
      const next = prev.slice()
      next[index] = { id, options }
      return next
    })
  }, [])

  const unregister = useCallback((id: string) => {
    setRegistrations((prev) => (prev.some((entry) => entry.id === id) ? prev.filter((entry) => entry.id !== id) : prev))
  }, [])

  const host = useMemo(() => ({ register, unregister }), [register, unregister])
  const options = registrations.length > 0 ? registrations[registrations.length - 1].options : EMPTY_OPTIONS
  return { host, options }
}

const EMPTY_OPTIONS: AppShellOptions = {}

export function AppShellHostProvider({ host, children }: { host: AppShellHost; children: React.ReactNode }) {
  return <AppShellHostContext.Provider value={host}>{children}</AppShellHostContext.Provider>
}

/** True when a persistent shell is mounted above (pages render inside its `<main>`). */
export function useInsideAppShell(): boolean {
  return useContext(AppShellHostContext) !== null
}

/**
 * Declare the chrome options for the current page. No-op without a persistent
 * host (the caller then renders the shell itself — see `AppShell`).
 *
 * Layout effects so the top bar title updates in the same frame the page
 * appears, rather than flashing the previous page's title.
 */
export function useAppShellOptions({ title, breadcrumbVendor, fillViewport }: AppShellOptions): void {
  const host = useContext(AppShellHostContext)
  const id = useId()

  useLayoutEffect(() => {
    if (!host) return
    host.register(id, { title, breadcrumbVendor, fillViewport })
  }, [host, id, title, breadcrumbVendor, fillViewport])

  useLayoutEffect(() => {
    if (!host) return
    return () => host.unregister(id)
  }, [host, id])
}
