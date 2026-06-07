"use client"

import React, { createContext, useContext, useEffect, useMemo } from "react"
import useSWR from "swr"
import { useAuth } from "@/lib/auth-context"
import { enterpriseApi } from "@/lib/api"

export interface EnterpriseBranding {
  logoUrl?: string | null
  primaryColor?: string | null
  customDomain?: string | null
  customDomainVerified?: boolean
  hidePoweredBy?: boolean
  emailFromName?: string | null
}

interface EnterpriseBrandingContextValue {
  branding: EnterpriseBranding
  isLoading: boolean
  refresh: () => Promise<void>
}

const DEFAULT_BRANDING: EnterpriseBranding = {
  logoUrl: null,
  primaryColor: "#6366f1",
  hidePoweredBy: false,
  emailFromName: "Gravitre",
}

const EnterpriseBrandingContext = createContext<EnterpriseBrandingContextValue>({
  branding: DEFAULT_BRANDING,
  isLoading: false,
  refresh: async () => {},
})

function applyBrandingCssVars(primaryColor: string | null | undefined) {
  if (typeof document === "undefined" || !primaryColor) return
  const root = document.documentElement
  root.style.setProperty("--brand-primary", primaryColor)
  root.style.setProperty("--primary", primaryColor)
  root.style.setProperty("--ring", primaryColor)
  root.style.setProperty("--sidebar-primary", primaryColor)
}

export function EnterpriseBrandingProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const { data, isLoading, mutate } = useSWR(
    user ? "/api/enterprise/branding" : null,
    () => enterpriseApi.getBranding(),
    { revalidateOnFocus: false }
  )

  const branding = useMemo<EnterpriseBranding>(() => {
    if (!data) return DEFAULT_BRANDING
    return {
      logoUrl: (data.logoUrl as string | null | undefined) ?? null,
      primaryColor: (data.primaryColor as string | null | undefined) ?? DEFAULT_BRANDING.primaryColor,
      customDomain: (data.customDomain as string | null | undefined) ?? null,
      customDomainVerified: Boolean(data.customDomainVerified),
      hidePoweredBy: Boolean(data.hidePoweredBy),
      emailFromName: (data.emailFromName as string | null | undefined) ?? DEFAULT_BRANDING.emailFromName,
    }
  }, [data])

  useEffect(() => {
    applyBrandingCssVars(branding.primaryColor)
  }, [branding.primaryColor])

  const value = useMemo(
    () => ({
      branding,
      isLoading,
      refresh: async () => {
        await mutate()
      },
    }),
    [branding, isLoading, mutate]
  )

  return (
    <EnterpriseBrandingContext.Provider value={value}>
      {children}
    </EnterpriseBrandingContext.Provider>
  )
}

export function useEnterpriseBranding() {
  return useContext(EnterpriseBrandingContext)
}
