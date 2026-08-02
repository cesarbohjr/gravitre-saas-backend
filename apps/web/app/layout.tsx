import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
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
import './globals.css'

const _geist = Geist({ subsets: ["latin"] });
const _geistMono = Geist_Mono({ subsets: ["latin"] });

// Allow pinch-to-zoom for accessibility (low-vision users).
// iOS auto-zoom on focus is prevented via 16px-minimum input font sizes, not by blocking zoom.
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f9fafb' },
    { media: '(prefers-color-scheme: dark)', color: '#0B0F14' },
  ],
}

export const metadata: Metadata = {
  metadataBase: new URL('https://gravitre.com'),
  title: {
    default: 'Gravitre - AI Operations Platform',
    template: '%s · Gravitre',
  },
  description: 'Enterprise AI operator console for managing workflows, runs, approvals, and AI-assisted operations',
  generator: 'v0.app',
  icons: {
    icon: '/images/gravitre-icon-black.png',
    apple: '/images/gravitre-icon-black.png',
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
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
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
                        {children}
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
