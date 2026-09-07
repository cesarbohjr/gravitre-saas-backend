import { DM_Mono } from 'next/font/google'

/**
 * DM Mono — Nodus Agent Template mono stack (next/font/google).
 * Paired with Inter Display for marketing + product chrome.
 */
export const dmMono = DM_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-dm-mono',
  display: 'swap',
})
