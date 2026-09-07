"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Icon, type IconName } from "@/lib/icons"
import { APP_ROUTES } from "@/lib/app-routes"
import { isSidebarItemActive } from "@/components/gravitre/sidebar-nav-config"
import { cn } from "@/lib/utils"

/**
 * Primary mobile destinations — subset of existing sidebar routes only.
 * Full nav remains in the slide drawer (hamburger).
 */
const MOBILE_BOTTOM_NAV: Array<{ name: string; href: string; icon: IconName }> = [
  { name: "Home", href: APP_ROUTES.home, icon: "home" },
  { name: "Chat", href: APP_ROUTES.gravitreAi, icon: "chat" },
  { name: "Agents", href: APP_ROUTES.agents, icon: "team" },
  { name: "Activity", href: APP_ROUTES.activity, icon: "checkCircle" },
  { name: "Approvals", href: APP_ROUTES.approvals, icon: "clipboardCheck" },
]

export function MobileBottomNav() {
  const pathname = usePathname()

  // Builder owns its own mobile chrome; don't stack a second bottom bar.
  if (pathname.includes("/builder")) {
    return null
  }

  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-divide bg-[color:var(--g-surface-1)]/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      <ul className="grid h-14 grid-cols-5">
        {MOBILE_BOTTOM_NAV.map((item) => {
          const active = isSidebarItemActive(pathname, item.href)
          return (
            <li key={item.href} className="min-w-0">
              <Link
                href={item.href}
                className={cn(
                  "flex h-full flex-col items-center justify-center gap-0.5 px-1 text-[10px] font-medium transition-colors",
                  active
                    ? "text-[color:var(--g-brand)]"
                    : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
                )}
              >
                <Icon
                  name={item.icon}
                  size="sm"
                  className={cn(active ? "text-[color:var(--g-brand)]" : "text-current")}
                />
                <span className="truncate">{item.name}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
