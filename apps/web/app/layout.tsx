import type { Metadata, Viewport } from 'next'
import { Analytics } from '@vercel/analytics/next'
import { RootProviders } from '@/components/root-providers'
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

export default async function RootLayout({
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
        <RootProviders>{children}</RootProviders>
        <Analytics />
      </body>
    </html>
  )
}
