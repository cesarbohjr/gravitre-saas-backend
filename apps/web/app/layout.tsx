import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import { ThemeProvider } from '@/components/theme-provider'
import { ViewModeProvider } from '@/lib/view-mode-context'
import { Toaster } from '@/components/ui/sonner'
import { NotificationProvider } from '@/components/gravitre/notification-center'
import { OnboardingProvider, OnboardingChecklist } from '@/components/gravitre/onboarding-checklist'
import { AuthProvider } from '@/lib/auth-context'
import { EntitlementsProvider } from '@/lib/entitlements-context'
import { UserProfileProvider } from '@/lib/user-profile-context'
import './globals.css'

const _geist = Geist({ subsets: ["latin"] });
const _geistMono = Geist_Mono({ subsets: ["latin"] });

// Disable auto-zoom on iOS Safari for inputs
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f9fafb' },
    { media: '(prefers-color-scheme: dark)', color: '#0B0F14' },
  ],
}

export const metadata: Metadata = {
  title: 'Gravitre - AI Operations Platform',
  description: 'Enterprise AI operator console for managing workflows, runs, approvals, and AI-assisted operations',
  generator: 'v0.app',
  icons: {
    icon: '/images/gravitre-icon.png',
    apple: '/images/gravitre-icon.png',
  },
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
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>
            <EntitlementsProvider>
              <UserProfileProvider>
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
            <Toaster position="bottom-right" richColors closeButton />
          </AuthProvider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
