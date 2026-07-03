"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Brain,
  Building2,
  CreditCard,
  Key,
  Plug,
  Shield,
  Sparkles,
  User,
  Users,
} from "lucide-react"
import { cn } from "@/lib/utils"

const SETTINGS_LINKS = [
  { href: "/settings/profile", label: "Account", icon: User },
  { href: "/settings", label: "Workspace", icon: Building2 },
  { href: "/settings/organizations", label: "Team", icon: Users },
  { href: "/settings/billing", label: "Billing", icon: CreditCard },
  { href: "/settings?section=security", label: "Security", icon: Shield },
  { href: "/connectors", label: "Integrations", icon: Plug },
  { href: "/settings/enterprise", label: "Intelligence", icon: Brain },
  { href: "/settings/team/permissions", label: "Permissions", icon: Sparkles },
] as const

function isActive(pathname: string, href: string) {
  const base = href.split("?")[0]
  if (base === "/settings") {
    return pathname === "/settings"
  }
  return pathname === base || pathname.startsWith(`${base}/`)
}

export function SettingsNav({ className }: { className?: string }) {
  const pathname = usePathname()

  return (
    <nav aria-label="Settings" className={cn("space-y-1", className)}>
      {SETTINGS_LINKS.map((item) => {
        const Icon = item.icon
        const active = isActive(pathname, item.href)
        return (
          <Link
            key={`${item.href}-${item.label}`}
            href={item.href}
            className={cn(
              "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
              active
                ? "bg-primary/10 font-medium text-foreground"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4 shrink-0" aria-hidden />
            {item.label}
          </Link>
        )
      })}
    </nav>
  )
}
