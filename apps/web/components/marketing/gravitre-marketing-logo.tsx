import Link from "next/link"
import { GravitreMark } from "@/components/brand/gravitre-mark"
import { cn } from "@/lib/utils"

type GravitreMarketingLogoProps = {
  className?: string
  height?: number
  href?: string
  priority?: boolean
}

function Mark({ className, size }: { className?: string; size: number }) {
  return <GravitreMark className={cn("w-auto", className)} style={{ height: size }} />
}

function wrap(image: React.ReactNode, href?: string) {
  if (!href) return <span className="inline-flex items-center">{image}</span>
  return (
    <Link
      href={href}
      aria-label="Gravitre home"
      className="inline-flex items-center rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {image}
    </Link>
  )
}

export function GravitreMarketingLogo({ className, height = 20, href = "/" }: GravitreMarketingLogoProps) {
  return wrap(<Mark size={height} className={className} />, href)
}

export function GravitreMarketingLogoWhite({
  className,
  height = 20,
  href = "/",
}: Omit<GravitreMarketingLogoProps, "priority">) {
  return wrap(<Mark size={height} className={className} />, href)
}
