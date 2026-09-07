import Link from "next/link"
import Image from "next/image"
import { cn } from "@/lib/utils"

/**
 * Gravitre mark for animation hubs / inline icons.
 * Replaces the Nodus geometric SVG so demos show Gravitre branding.
 */
export function LogoSVG({
  className,
  ..._props
}: React.SVGProps<SVGSVGElement>) {
  const brandTint = typeof className === "string" && className.includes("text-brand")
  return (
    <Image
      src={
        brandTint
          ? "/images/gravitre-icon-green-1024.png"
          : "/images/gravitre-icon-black.png"
      }
      alt=""
      width={32}
      height={32}
      className={cn("h-6 w-6 object-contain", className)}
      aria-hidden
    />
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
