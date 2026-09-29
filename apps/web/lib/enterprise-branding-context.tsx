"use client"

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  useCallback,
  type ReactNode,
} from "react"
import useSWR from "swr"
import { useAuth } from "@/lib/auth-context"
import { enterpriseApi } from "@/lib/api"
import type { EnterpriseBranding } from "@/types/api"

/**
 * Enterprise white-label branding.
 *
 * Fetches the org branding config and applies the org primary color to the
 * global CSS custom properties (--primary, --ring, --sidebar-primary, etc).
 * The settings page can push a transient "preview" override so admins see
 * changes live before saving.
 */

interface BrandingPreview {
  logoUrl?: string | null
  primaryColor?: string | null
  hidePoweredBy?: boolean
}

interface EnterpriseBrandingContextType {
  branding: EnterpriseBranding | null
  isLoading: boolean
  /** Effective values after applying any live preview override. */
  effectiveLogoUrl: string | null
  effectivePrimaryColor: string | null
  effectiveHidePoweredBy: boolean
  /** Push a transient preview (settings page). Pass null to clear. */
  setPreview: (preview: BrandingPreview | null) => void
  /** Re-fetch branding from the API (after a save). */
  refresh: () => void
}

const EnterpriseBrandingContext = createContext<EnterpriseBrandingContextType | undefined>(undefined)

const HEX_RE = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i

function normalizeHex(hex: string): string | null {
  if (!HEX_RE.test(hex)) return null
  let value = hex.slice(1)
  if (value.length === 3) {
    value = value
      .split("")
      .map((c) => c + c)
      .join("")
  }
  return `#${value.toLowerCase()}`
}

function relativeLuminance(normalized: string): number {
  const r = parseInt(normalized.slice(1, 3), 16) / 255
  const g = parseInt(normalized.slice(3, 5), 16) / 255
  const b = parseInt(normalized.slice(5, 7), 16) / 255
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4))
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

/** Relative luminance to pick a readable foreground (black/white) on the brand color. */
function readableForeground(hex: string): string {
  const normalized = normalizeHex(hex)
  if (!normalized) return "oklch(0.99 0 0)"
  return relativeLuminance(normalized) > 0.5 ? "oklch(0.15 0 0)" : "oklch(0.99 0 0)"
}

/** WCAG 3:1 non-text contrast against the dark theme's near-black surfaces. */
export function brandColorReadableOnDark(hex: string): boolean {
  const normalized = normalizeHex(hex)
  if (!normalized) return false
  return (relativeLuminance(normalized) + 0.05) / 0.053 >= 3
}

const BRAND_VARS = ["--primary", "--ring", "--sidebar-primary", "--sidebar-ring", "--info", "--chart-1"]
const BRAND_STYLE_ID = "gravitre-enterprise-brand"

/**
 * Brand variables live in a scoped stylesheet rather than inline on <html>, so a dark
 * brand color never overrides the dark theme's primary with an unreadable value.
 */
export function brandColorCss(color: string | null): string | null {
  if (!color) return null
  const normalized = normalizeHex(color)
  if (!normalized) return null
  const fg = readableForeground(normalized)
  const decls = [
    ...BRAND_VARS.map((v) => `${v}: ${normalized};`),
    `--primary-foreground: ${fg};`,
    `--sidebar-primary-foreground: ${fg};`,
  ].join(" ")
  const light = `:root:not(.dark) { ${decls} }`
  return brandColorReadableOnDark(normalized) ? `${light} .dark { ${decls} }` : light
}

function applyBrandColor(color: string | null) {
  if (typeof document === "undefined") return
  const root = document.documentElement
  BRAND_VARS.forEach((v) => root.style.removeProperty(v))
  root.style.removeProperty("--primary-foreground")
  root.style.removeProperty("--sidebar-primary-foreground")
  const css = brandColorCss(color)
  let tag = document.getElementById(BRAND_STYLE_ID) as HTMLStyleElement | null
  if (!css) {
    tag?.remove()
    return
  }
  if (!tag) {
    tag = document.createElement("style")
    tag.id = BRAND_STYLE_ID
    document.head.appendChild(tag)
  }
  tag.textContent = css
}

export function EnterpriseBrandingProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [preview, setPreview] = useState<BrandingPreview | null>(null)

  const { data, isLoading, mutate } = useSWR<EnterpriseBranding>(
    user ? "enterprise-branding" : null,
    () => enterpriseApi.getBranding(),
    {
      revalidateOnFocus: false,
      shouldRetryOnError: false,
    },
  )

  const branding = data ?? null

  const effectivePrimaryColor = useMemo(() => {
    if (preview && preview.primaryColor !== undefined) return preview.primaryColor
    return branding?.primaryColor ?? null
  }, [preview, branding])

  const effectiveLogoUrl = useMemo(() => {
    if (preview && preview.logoUrl !== undefined) return preview.logoUrl
    return branding?.logoUrl ?? null
  }, [preview, branding])

  const effectiveHidePoweredBy = useMemo(() => {
    if (preview && preview.hidePoweredBy !== undefined) return Boolean(preview.hidePoweredBy)
    return Boolean(branding?.hidePoweredBy)
  }, [preview, branding])

  // Apply / revert brand color CSS variables globally.
  useEffect(() => {
    applyBrandColor(effectivePrimaryColor)
    return () => {
      // On unmount, leave applied (provider lives at root). No cleanup needed.
    }
  }, [effectivePrimaryColor])

  const refresh = useCallback(() => {
    void mutate()
  }, [mutate])

  const value = useMemo<EnterpriseBrandingContextType>(
    () => ({
      branding,
      isLoading,
      effectiveLogoUrl,
      effectivePrimaryColor,
      effectiveHidePoweredBy,
      setPreview,
      refresh,
    }),
    [branding, isLoading, effectiveLogoUrl, effectivePrimaryColor, effectiveHidePoweredBy, refresh],
  )

  return (
    <EnterpriseBrandingContext.Provider value={value}>{children}</EnterpriseBrandingContext.Provider>
  )
}

export function useEnterpriseBranding() {
  const context = useContext(EnterpriseBrandingContext)
  if (context === undefined) {
    throw new Error("useEnterpriseBranding must be used within an EnterpriseBrandingProvider")
  }
  return context
}
