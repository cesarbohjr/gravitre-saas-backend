import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { ThemeProvider } from '@/components/theme-provider'
import { MotionProvider } from '@/components/motion-provider'
import { ViewModeProvider } from '@/lib/view-mode-context'
import { Toaster } from '@/components/ui/sonner'
import { NotificationProvider } from '@/components/gravitre/notification-center'
import { OnboardingProvider, OnboardingChecklist } from '@/components/gravitre/onboarding-checklist'
import { AuthProvider } from '@/lib/auth-context'
import { OrgSyncBootstrap } from '@/components/gravitre/org-sync-bootstrap'
import { EnterpriseBrandingProvider } from '@/lib/enterprise-branding-context'
import { EntitlementsProvider } from '@/lib/entitlements-context'
import { UserProfileProvider } from '@/lib/user-profile-context'
import { AccountProfileSync } from '@/components/gravitre/account-profile-sync'
import { GravitreAIWorkspaceProvider } from '@/components/gravitre/ai-workspace-provider'
import { GravitreAIHelper } from '@/components/gravitre/ai-helper'
import { GravitreAIShortcutListener } from '@/components/gravitre/ai-shortcut-listener'
import { GravitreAIPresenceAnnouncer } from '@/components/gravitre/ai-presence-announcer'
import { interDisplay } from '@/fonts/inter-display/inter'
import { dmMono } from '@/fonts/dm-mono'
import './globals.css'

// Allow pinch-to-zoom for accessibility (low-vision users).
// iOS auto-zoom on focus is prevented via 16px-minimum input font sizes, not by blocking zoom.
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  // Light-first only (Nodus full-match Gate 0 decision).
  themeColor: [{ media: '(prefers-color-scheme: light)', color: '#ffffff' }],
}

export const metadata: Metadata = {
  metadataBase: new URL('https://gravitre.app'),
  title: {
    default: 'Gravitre - AI Operations Platform',
    template: '%s · Gravitre',
  },
  description: 'Enterprise AI operator console for managing workflows, runs, approvals, and AI-assisted operations',
  generator: 'v0.app',
  // Favicon set is the green-background mark. The previous icon was the BLACK
  // logo, which disappeared against dark browser chrome — the common case, since
  // the tab strip is dark in dark mode on every major browser. The green tile
  // reads at 16px on light and dark chrome alike.
  //
  // Sizes are explicit rather than pointing every slot at one 1024px PNG: that
  // made the browser download ~139KB to paint a 16px tab icon. Real sizes are
  // 501b–1.6KB.
  icons: {
    icon: [
      // .ico first for legacy/bookmark surfaces that ignore <link> sizes.
      { url: '/favicon.ico', sizes: '16x16 32x32 48x48' },
      { url: '/icon-16x16.png', type: 'image/png', sizes: '16x16' },
      { url: '/icon-32x32.png', type: 'image/png', sizes: '32x32' },
      { url: '/icon-192x192.png', type: 'image/png', sizes: '192x192' },
      { url: '/icon-512x512.png', type: 'image/png', sizes: '512x512' },
    ],
    // Opaque: the artwork has transparent rounded corners, and iOS composites
    // touch icons on black before applying its own mask, so an unflattened
    // version shows black wedges in the corners.
    apple: [{ url: '/apple-icon.png', sizes: '180x180' }],
  },
}

const requiredEnvVars = [
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_ANON_KEY',
  'FASTAPI_BASE_URL',
] as const

for (const key of requiredEnvVars) {
  if (!process.env[key]) {
    console.error(`Missing required env var: ${key}`)
  }
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${interDisplay.variable} ${dmMono.variable}`}
    >
      <body className="font-sans antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          forcedTheme="light"
          enableSystem={false}
          disableTransitionOnChange
        >
          <MotionProvider>
          <AuthProvider>
            <OrgSyncBootstrap />
            <EnterpriseBrandingProvider>
              <EntitlementsProvider>
                <UserProfileProvider>
                  <AccountProfileSync />
                  <NotificationProvider>
                    <OnboardingProvider>
                      <ViewModeProvider>
                        {/*
                          Mounted once, above every per-page <AppShell> — see
                          docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
                          Finding A5 / Part B1. Must never move inside a
                          per-page tree, or it loses the one property Phase 2+
                          depends on: surviving route navigation unremounted.
                        */}
                        <GravitreAIWorkspaceProvider>
                          {children}
                          {/*
                            Phase 2 — bottom-left persistent presence bubble.
                            Gated by NEXT_PUBLIC_AI_FLOAT_ENABLED (default
                            off) inside the component itself; renders null
                            when the flag is off, so this line is not itself
                            a visible behavior change. See
                            components/gravitre/ai-helper.tsx.
                          */}
                          <GravitreAIHelper />
                          {/*
                            Phase 3 — global keyboard shortcut listener
                            (Ctrl/Cmd+Shift+L) and aria-live presentation-
                            mode announcer. Both render nothing and are
                            internally gated by NEXT_PUBLIC_AI_FLOAT_ENABLED
                            (default off), so mounting them is not itself a
                            visible behavior change. See
                            components/gravitre/ai-shortcut-listener.tsx and
                            components/gravitre/ai-presence-announcer.tsx.
                          */}
                          <GravitreAIShortcutListener />
                          <GravitreAIPresenceAnnouncer />
                        </GravitreAIWorkspaceProvider>
                      </ViewModeProvider>
                      <OnboardingChecklist />
                    </OnboardingProvider>
                  </NotificationProvider>
                </UserProfileProvider>
              </EntitlementsProvider>
            </EnterpriseBrandingProvider>
            <Toaster position="bottom-right" />
          </AuthProvider>
          </MotionProvider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
