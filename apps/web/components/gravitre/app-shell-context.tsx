"use client"

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

export interface AppShellMeta {
  title?: string
  breadcrumbVendor?: string
}

interface AppShellMetaContextValue {
  meta: AppShellMeta
  setMeta: (meta: AppShellMeta) => void
}

const AppShellPresenceContext = createContext(false)
const AppShellMetaContext = createContext<AppShellMetaContextValue | null>(null)

export function AppShellPresenceProvider({
  children,
  active = true,
}: {
  children: ReactNode
  active?: boolean
}) {
  return (
    <AppShellPresenceContext.Provider value={active}>
      {children}
    </AppShellPresenceContext.Provider>
  )
}

export function AppShellMetaProvider({ children }: { children: ReactNode }) {
  const [meta, setMetaState] = useState<AppShellMeta>({})
  const setMeta = useCallback((next: AppShellMeta) => {
    setMetaState((prev) => {
      if (prev.title === next.title && prev.breadcrumbVendor === next.breadcrumbVendor) {
        return prev
      }
      return next
    })
  }, [])

  const value = useMemo(() => ({ meta, setMeta }), [meta, setMeta])

  return (
    <AppShellMetaContext.Provider value={value}>
      {children}
    </AppShellMetaContext.Provider>
  )
}

export function useAppShellNested(): boolean {
  return useContext(AppShellPresenceContext)
}

export function useAppShellMeta(): AppShellMetaContextValue | null {
  return useContext(AppShellMetaContext)
}
