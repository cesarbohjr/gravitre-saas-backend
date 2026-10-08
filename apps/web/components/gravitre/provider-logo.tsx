"use client"

import { createElement, useState } from "react"
import {
  ChartColumn,
  Contact,
  Cpu,
  Database,
  GraduationCap,
  HardDrive,
  Landmark,
  LayoutGrid,
  Library,
  LifeBuoy,
  Mail,
  Megaphone,
  MessageSquare,
  PenTool,
  Plug,
  Server,
  ShoppingBag,
  Users,
  Workflow,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { resolveProvider, type ProviderCategory, type ProviderEntry } from "@/lib/provider-registry"

/**
 * One logo primitive for every provider / vendor / connector surface.
 * Fixed square slot, mark kept at its intrinsic aspect ratio, no brand tile.
 * Brand colour is preserved; dark theme swaps to the registry's dark variant.
 */
export const PROVIDER_LOGO_SIZES = {
  /** Inline with 12–13px text (breadcrumbs, chips). */
  sm: { slot: "h-4 w-4", glyph: "h-4 w-4", plate: "p-px rounded-[3px]" },
  /** Default — lists, nodes, cards. */
  md: { slot: "h-5 w-5", glyph: "h-[18px] w-[18px]", plate: "p-[2px] rounded" },
  /** Detail headers. */
  lg: { slot: "h-6 w-6", glyph: "h-5 w-5", plate: "p-[3px] rounded-[5px]" },
} as const

export type ProviderLogoSize = keyof typeof PROVIDER_LOGO_SIZES

const CATEGORY_GLYPH: Record<ProviderCategory, LucideIcon> = {
  crm: Contact,
  marketing: Megaphone,
  analytics: ChartColumn,
  sales: Contact,
  knowledge: Library,
  finance: Landmark,
  commerce: ShoppingBag,
  communication: MessageSquare,
  email: Mail,
  devops: Server,
  productivity: LayoutGrid,
  automation: Workflow,
  support: LifeBuoy,
  hr: Users,
  storage: HardDrive,
  data: Database,
  learning: GraduationCap,
  design: PenTool,
  ai: Cpu,
  generic: Plug,
}

export function providerFallbackGlyph(category?: ProviderCategory): LucideIcon {
  return category ? CATEGORY_GLYPH[category] : Plug
}

export interface ProviderLogoProps {
  /** Canonical provider id, vendor key, catalog type or display name. */
  provider?: string | null
  /** Accessible name override (defaults to the registry name, then `provider`). */
  label?: string
  size?: ProviderLogoSize
  /** Pin the light-theme treatment (always-light marketing surfaces). */
  theme?: "auto" | "light"
  /** Hide from assistive tech when an adjacent visible label already names the provider. */
  decorative?: boolean
  className?: string
}

export function ProviderLogo({
  provider,
  label,
  size = "md",
  theme = "auto",
  decorative = false,
  className,
}: ProviderLogoProps) {
  const entry = resolveProvider(provider)
  const [failed, setFailed] = useState(false)
  const token = PROVIDER_LOGO_SIZES[size]
  const name = label || entry?.name || provider || "Provider"
  const a11y = decorative
    ? ({ "aria-hidden": true } as const)
    : ({ role: "img", "aria-label": name } as const)

  if (!entry || entry.source === "fallback" || !entry.src || failed) {
    return (
      <span
        {...a11y}
        data-provider={entry?.id ?? provider ?? undefined}
        data-provider-fallback=""
        className={cn("inline-flex shrink-0 items-center justify-center text-muted-foreground", token.slot, className)}
      >
        <FallbackGlyph category={entry?.category} className={token.glyph} />
      </span>
    )
  }

  return (
    <span
      {...a11y}
      data-provider={entry.id}
      data-provider-source={entry.source}
      className={cn("inline-flex shrink-0 items-center justify-center", token.slot, className)}
    >
      <ProviderMark entry={entry} theme={theme} plate={token.plate} onError={() => setFailed(true)} />
    </span>
  )
}

function FallbackGlyph({ category, className }: { category?: ProviderCategory; className: string }) {
  return createElement(providerFallbackGlyph(category), { className, strokeWidth: 1.75, "aria-hidden": true })
}

function ProviderMark({
  entry,
  theme,
  plate,
  onError,
}: {
  entry: ProviderEntry
  theme: "auto" | "light"
  plate: string
  onError: () => void
}) {
  const img = (src: string, extra?: string) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      aria-hidden
      loading="lazy"
      decoding="async"
      draggable={false}
      onError={onError}
      className={cn("block max-h-full max-w-full object-contain", extra)}
    />
  )

  const swapsInDark = theme === "auto" && entry.srcDark && entry.srcDark !== entry.src
  const lightPlate = entry.lightPlate
    ? cn("bg-[color:var(--g-carbon)]", theme === "auto" && "dark:bg-transparent dark:p-0", plate)
    : undefined
  const darkPlate = entry.darkPlate && theme === "auto" ? cn("dark:bg-[color:var(--g-bone)]", plate) : undefined

  return (
    <span className={cn("flex h-full w-full items-center justify-center", lightPlate, darkPlate)}>
      {swapsInDark ? (
        <>
          {img(entry.src!, "dark:hidden")}
          {img(entry.srcDark!, "hidden dark:block")}
        </>
      ) : (
        img(entry.src!)
      )}
    </span>
  )
}