import { headers } from "next/headers"
import type { ReactNode } from "react"
import { Navbar } from "@/components/marketing/nodus/navbar"
import { Footer } from "@/components/marketing/nodus/footer"
import { DivideX } from "@/components/marketing/nodus/divide"
import { MarketingThemeLock } from "@/components/marketing/marketing-theme-lock"

const AUTH_FOOTER_SLIM_PATHS = new Set(["/login", "/get-started", "/forgot-password"])

/**
 * Marketing chrome — Nodus Agent Template layout (light-first, Gravitre brand).
 * Server shell: navbar SSR, footer lazy-loaded below the fold.
 */
export async function MarketingChrome({ children }: { children: ReactNode }) {
  const pathname = (await headers()).get("x-pathname") ?? ""
  const slimFooter = AUTH_FOOTER_SLIM_PATHS.has(pathname)

  return (
    <div className="min-h-screen overflow-x-hidden bg-white text-charcoal-900" data-marketing-canvas="daylight">
      <MarketingThemeLock />
      <Navbar />
      <DivideX />
      {children}
      <DivideX />
      <Footer variant={slimFooter ? "slim" : "full"} />
    </div>
  )
}
