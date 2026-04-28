"use client"

import { createContext, useContext, useMemo, type ReactNode } from "react"
import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"

type Tier = "free" | "node" | "control" | "command"

type EntitlementsPayload = {
  entitlements?: {
    tier?: Tier
    status?: string
    limits?: Record<string, number | null>
    usage?: Record<string, number>
    features?: Record<string, boolean>
    addons?: Array<string | Record<string, unknown>>
    lite_seats?: number
    seat_count?: number
  }
}

interface EntitlementsContextValue {
  tier: Tier
  status: string
  loading: boolean
  canAccess: (feature: string) => boolean
  quotaRemaining: (resource: string) => number | null
  isAtLimit: (resource: string) => boolean
  addons: Array<string | Record<string, unknown>>
}

const EntitlementsContext = createContext<EntitlementsContextValue | undefined>(undefined)

const FREE_LIMITS: Record<string, number | null> = {
  workflows: 3,
  agents: 1,
  connectors: 2,
  runs_per_month: 200,
  operator_sessions_concurrent: 1,
  lite_seats_included: 0,
}

export function EntitlementsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()

  const { data, isLoading } = useSWR<EntitlementsPayload>(
    user ? "/api/entitlements" : null,
    apiFetcher,
    { revalidateOnFocus: false, refreshInterval: 30000 }
  )

  const value = useMemo<EntitlementsContextValue>(() => {
    const entitlements = data?.entitlements ?? {}
    const tier = entitlements.tier ?? "free"
    const status = entitlements.status ?? "inactive"
    const limits = entitlements.limits ?? FREE_LIMITS
    const usage = entitlements.usage ?? {}
    const features = entitlements.features ?? {}
    const addons = entitlements.addons ?? []

    return {
      tier,
      status,
      loading: isLoading,
      canAccess: (feature: string) => Boolean(features[feature]),
      quotaRemaining: (resource: string) => {
        const limit = limits[resource]
        if (limit === null || limit === undefined) return null
        const consumed = Number(usage[resource] ?? 0)
        return Math.max(Number(limit) - consumed, 0)
      },
      isAtLimit: (resource: string) => {
        const limit = limits[resource]
        if (limit === null || limit === undefined) return false
        const consumed = Number(usage[resource] ?? 0)
        return consumed >= Number(limit)
      },
      addons,
    }
  }, [data, isLoading])

  return <EntitlementsContext.Provider value={value}>{children}</EntitlementsContext.Provider>
}

export function useEntitlements() {
  const context = useContext(EntitlementsContext)
  if (!context) {
    throw new Error("useEntitlements must be used within an EntitlementsProvider")
  }
  return context
}

