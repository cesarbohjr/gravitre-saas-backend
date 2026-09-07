import Link from "next/link"
import Image from "next/image"
import type { SVGProps } from "react"
import { cn } from "@/lib/utils"

/**
 * Gravitre mark for animation hubs / chat avatars.
 * Dense two-bar SVG (fills the viewBox like the original Nodus geometric mark).
 * Prefer this over padded PNG tiles so logos read at the same visual weight.
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
      {/* Two parallel slanted bars — ~70% of the box, matching Nodus fill weight */}
      <g transform="translate(12 12) skewX(-14) translate(-12 -12)">
        <rect x="3.5" y="5.2" width="17" height="4.6" rx="2.1" />
        <rect x="3.5" y="14.2" width="17" height="4.6" rx="2.1" />
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
