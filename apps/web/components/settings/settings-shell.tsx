"use client"

import { usePathname } from "next/navigation"
import { SettingsNav } from "@/components/settings/settings-nav"

const FULL_WIDTH_PREFIXES = ["/settings/billing/checkout"]

export function SettingsShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const fullWidth = FULL_WIDTH_PREFIXES.some((prefix) => pathname.startsWith(prefix))

  if (fullWidth) {
    return <>{children}</>
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 md:flex-row md:p-6">
      <aside className="md:w-56 md:shrink-0">
        <p className="mb-3 hidden text-xs font-semibold uppercase tracking-wide text-muted-foreground md:block">
          Settings
        </p>
        <SettingsNav />
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  )
}
