import localFont from 'next/font/local'

/** Display voice specified by Figma Emerald Intelligence, nodes 8:20 and 17:10. */
export const spaceGrotesk = localFont({
  src: './SpaceGrotesk-Variable.ttf',
  weight: '300 700',
  variable: '--font-space-grotesk',
  display: 'swap',
  preload: false,
})
