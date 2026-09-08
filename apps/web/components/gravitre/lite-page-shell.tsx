"use client"

/**
 * Lite pages share Admin chrome (AppShell + GravitrePageHeader). Content stays simplified;
 * only nav IA and page body differ from Admin hubs.
 */

import type { LucideIcon } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"

interface LitePageShellProps {
  title: string
  description?: string
  icon?: LucideIcon
  actions?: React.ReactNode
  headerChildren?: React.ReactNode
  loading?: boolean
  loadingLabel?: string
  children: React.ReactNode
}

export function LitePageShell({
  title,
  description,
  icon: Icon,
  actions,
  headerChildren,
  loading = false,
  loadingLabel = "Loading",
  children,
}: LitePageShellProps) {
  if (loading) {
    return (
      <AppShell title={title}>
        <CenteredLoader size="lg" label={loadingLabel} fill="parent" />
      </AppShell>
    )
  }

  return (
    <AppShell title={title}>
      <GravitrePageHeader
        title={title}
        description={description}
        icon={Icon ? <Icon className="h-5 w-5" /> : undefined}
        actions={actions}
      >
        {headerChildren}
      </GravitrePageHeader>
      <div className="space-y-4 p-4 sm:p-6">{children}</div>
    </AppShell>
  )
}
