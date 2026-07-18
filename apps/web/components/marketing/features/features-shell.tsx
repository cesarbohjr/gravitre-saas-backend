"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion } from "framer-motion"
import { ArrowRight, ChevronRight } from "lucide-react"
import {
  FEATURES_NAV,
  FEATURES_NAV_GROUPS,
  getFeaturesNavItem,
  type FeaturesSectionId,
} from "@/lib/features-nav"

export function FeaturesSubHero({ sectionId }: { sectionId: FeaturesSectionId }) {
  const item = FEATURES_NAV.find((entry) => entry.id === sectionId)
  if (!item) return null
  const Icon = item.icon

  return (
    <section className="relative overflow-hidden border-b border-zinc-200 bg-gradient-to-b from-emerald-50/80 via-white to-white pt-28 pb-12 lg:pt-32">
      <motion.div
        className="pointer-events-none absolute -top-24 right-0 h-72 w-72 rounded-full bg-emerald-100/60 blur-3xl"
        animate={{ scale: [1, 1.08, 1], opacity: [0.35, 0.5, 0.35] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="relative mx-auto max-w-4xl px-6">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}>
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50/80 px-3 py-1.5">
            <Icon className="h-4 w-4 text-emerald-600" />
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700">{item.group}</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900 sm:text-4xl lg:text-5xl text-balance">
            {item.label}
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-zinc-600 text-pretty">{item.description}</p>
        </motion.div>
      </div>
    </section>
  )
}

export function FeaturesShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const isHub = pathname === "/features"
  const active = getFeaturesNavItem(pathname)

  return (
    <div className="min-h-screen bg-white">
      {!isHub ? (
        <div className="border-b border-zinc-200 bg-zinc-50/80">
          <div className="mx-auto flex max-w-7xl items-center gap-2 px-6 py-3 text-sm text-zinc-500">
            <Link href="/features" className="hover:text-zinc-900 transition-colors">
              Features
            </Link>
            <ChevronRight className="h-3.5 w-3.5" />
            <span className="font-medium text-zinc-900">{active?.label ?? "Explore"}</span>
          </div>
        </div>
      ) : null}

      <div className={`mx-auto max-w-7xl ${isHub ? "" : "lg:grid lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-10"}`}>
        {!isHub ? (
          <aside className="hidden lg:block border-r border-zinc-200 py-10 pr-6">
            <p className="mb-4 px-3 text-xs font-semibold uppercase tracking-wider text-zinc-400">Explore</p>
            <nav className="space-y-6">
              {FEATURES_NAV_GROUPS.map((group) => (
                <div key={group}>
                  <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{group}</p>
                  <ul className="space-y-1">
                    {FEATURES_NAV.filter((item) => item.group === group && item.id !== "overview").map((item) => {
                      const isActive = pathname === item.href
                      const Icon = item.icon
                      return (
                        <li key={item.href}>
                          <Link
                            href={item.href}
                            className={`group flex items-start gap-3 rounded-xl px-3 py-2.5 text-sm transition-all ${
                              isActive
                                ? "bg-emerald-50 text-emerald-900 ring-1 ring-emerald-200"
                                : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
                            }`}
                          >
                            <Icon
                              className={`mt-0.5 h-4 w-4 shrink-0 ${
                                isActive ? "text-emerald-600" : "text-zinc-400 group-hover:text-zinc-600"
                              }`}
                            />
                            <span className="font-medium leading-snug">{item.label}</span>
                          </Link>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              ))}
            </nav>
            <Link
              href="/features"
              className="mt-8 inline-flex items-center gap-2 px-3 text-sm font-medium text-emerald-700 hover:text-emerald-600"
            >
              Back to overview
              <ArrowRight className="h-4 w-4" />
            </Link>
          </aside>
        ) : null}

        {!isHub ? (
          <div className="border-b border-zinc-200 bg-white lg:hidden">
            <div className="flex gap-2 overflow-x-auto px-4 py-3 scrollbar-none">
              <Link
                href="/features"
                className="shrink-0 rounded-full border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600"
              >
                Overview
              </Link>
              {FEATURES_NAV.filter((item) => item.id !== "overview").map((item) => {
                const isActive = pathname === item.href
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                      isActive
                        ? "bg-emerald-600 text-white"
                        : "border border-zinc-200 text-zinc-600 hover:border-zinc-300"
                    }`}
                  >
                    {item.label}
                  </Link>
                )
              })}
            </div>
          </div>
        ) : null}

        <div className={isHub ? "" : "min-w-0"}>{children}</div>
      </div>
    </div>
  )
}
