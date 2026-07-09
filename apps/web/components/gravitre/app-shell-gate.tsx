"use client"

import { usePathname } from "next/navigation"
import { shouldMountAppShell } from "@/lib/app-shell-paths"
import { AppShell } from "./app-shell"

/**
 * Mounts a single persistent AppShell for authenticated app routes so the
 * sidebar/top bar survive client-side navigations (no full document reload).
 * Page-level <AppShell title="…"> wrappers become nested no-ops that only
 * publish title/breadcrumb metadata.
 */
export function AppShellGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  if (!shouldMountAppShell(pathname)) {
    return <>{children}</>
  }

  return <AppShell>{children}</AppShell>
}
