import localFont from 'next/font/local'

/**
 * Inter Display — licensed via Nodus Agent Template (Aceternity).
 * Source mirrored from vendor/nodus-agent-template/fonts (vendor tree gitignored).
 * Brand SOT: Nodus full-match Gate 0 / Phase 3–4.
 */
export const interDisplay = localFont({
  src: [
    { path: './InterDisplay-Light.ttf', weight: '300', style: 'normal' },
    { path: './InterDisplay-Regular.ttf', weight: '400', style: 'normal' },
    { path: './InterDisplay-Medium.ttf', weight: '500', style: 'normal' },
    { path: './InterDisplay-SemiBold.ttf', weight: '600', style: 'normal' },
    { path: './InterDisplay-Bold.ttf', weight: '700', style: 'normal' },
    { path: './InterDisplay-ExtraBold.ttf', weight: '800', style: 'normal' },
    { path: './InterDisplay-Black.ttf', weight: '900', style: 'normal' },
  ],
  variable: '--font-inter-display',
  display: 'swap',
})
