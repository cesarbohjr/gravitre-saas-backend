"use client"

import { useEffect, useRef, type ReactNode } from "react"
import { usePathname } from "next/navigation"
import { ThemeProvider } from "@/components/theme-provider"
import { MotionProvider } from "@/components/motion-provider"
import { AuthProvider } from "@/lib/auth-context"
import { usesMarketingProviderTree } from "@/lib/is-marketing-route"

/**
 * Minimal provider tree for anonymous marketing routes — skips the operator
 * app shell (AI workspace, entitlements, onboarding, etc.) so Lighthouse /
 * crawlers do not download and hydrate that JS on / and /pricing.
 */
export function MarketingProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      forcedTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      <MotionProvider>
        <AuthProvider>
          <OperatorRouteGuard>{children}</OperatorRouteGuard>
        </AuthProvider>
      </MotionProvider>
    </ThemeProvider>
  )
}

/**
 * Stops an operator route from rendering inside the marketing provider tree.
 *
 * `RootProviders` chooses between this tree and `AppProviders` from the
 * `x-gravitre-marketing` request header, and the root layout is only rendered on
 * a full document load — the App Router preserves it across client-side
 * navigation. So the choice is frozen at the first page load: navigate from a
 * marketing route to an operator route without a document request and the
 * operator shell mounts here, missing every provider it requires.
 *
 * That is not a soft failure. `sidebar.tsx` and `top-bar.tsx` call the strict
 * `useViewMode()`, which throws, taking the whole page down to an error boundary
 * reading "useViewMode must be used within a ViewModeProvider". Six more
 * providers behind it throw the same way (onboarding, entitlements, user
 * profile, enterprise branding, notifications-required, AI workspace), so
 * patching one hook would only move the crash.
 *
 * `/login` and `/get-started` are both marketing routes and both enter the app
 * with `router.replace` / `router.push`, so this is reachable from the primary
 * sign-in path.
 *
 * The repair is a real document request for the same URL, which re-runs the
 * proxy, sets the correct header and mounts `AppProviders`. Children are held
 * back until then, because the crash happens while they render — an effect alone
 * would fire too late. This cannot loop: a mismatch means the path is not a
 * marketing-tree path, so the reload lands on `AppProviders` and this guard is
 * no longer mounted.
 */
function OperatorRouteGuard({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const mismatched = Boolean(pathname) && !usesMarketingProviderTree(pathname)
  const repairedFor = useRef<string | null>(null)

  useEffect(() => {
    if (!mismatched || !pathname) return
    if (repairedFor.current === pathname) return
    repairedFor.current = pathname
    const { search, hash } = window.location
    window.location.replace(`${pathname}${search}${hash}`)
  }, [mismatched, pathname])

  if (mismatched) {
    // Deliberately plain: this renders with none of the operator providers
    // mounted, so it must not use any app chrome. No product claims here — it is
    // a sub-second bridge to the document load.
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex min-h-screen items-center justify-center px-6 text-center text-sm text-neutral-500"
      >
        Loading…
      </div>
    )
  }

  return <>{children}</>
}
