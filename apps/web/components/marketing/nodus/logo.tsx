import Link from "next/link"
import Image from "next/image"
import type { SVGProps } from "react"
import { cn } from "@/lib/utils"

/**
 * Gravitre mark for animation hubs / chat avatars.
 * Dense two-bar SVG — thick bars nearly fill the viewBox so visual weight
 * matches the original Nodus geometric mark (not a thin outline).
 */
export function LogoSVG({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("size-full shrink-0 text-current", className)}
      aria-hidden
      {...props}
    >
      {/* ~85% fill: thick bars + tight gap, same optical mass as Nodus squares */}
      <g transform="translate(12 12) skewX(-14) translate(-12 -12)">
        <rect x="1.5" y="3.2" width="21" height="7" rx="2.4" />
        <rect x="1.5" y="13.8" width="21" height="7" rx="2.4" />
      </g>
    </svg>
  )
}

export const Logo = () => {
  return (
    <Link href="/" className="flex items-center gap-2">
      <Image
        src="/images/gravitre-logo-black.png"
        alt="Gravitre"
        width={140}
        height={40}
        className="h-8 w-auto"
        priority
      />
    </Link>
  )
}
