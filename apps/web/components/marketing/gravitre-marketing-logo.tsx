import Image from "next/image"
import Link from "next/link"
import { cn } from "@/lib/utils"

type GravitreMarketingLogoProps = {
  className?: string
  height?: number
  href?: string
  priority?: boolean
}

function GravitreMark({
  className,
  size,
  priority,
}: {
  className?: string
  size: number
  priority?: boolean
}) {
  return (
    <Image
      src="/images/gravitre-mark.png"
      alt="Gravitre"
      width={size}
      height={size}
      priority={priority}
      className={cn("shrink-0 rounded-[22%]", className)}
      style={{ width: size, height: size }}
    />
  )
}

function wrap(image: React.ReactNode, href?: string) {
  if (!href) return <span className="inline-flex items-center">{image}</span>
  return (
    <Link
      href={href}
      className="inline-flex items-center rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {image}
    </Link>
  )
}

export function GravitreMarketingLogo({
  className,
  height = 40,
  href = "/",
  priority = false,
}: GravitreMarketingLogoProps) {
  return wrap(<GravitreMark size={height} priority={priority} className={className} />, href)
}

export function GravitreMarketingLogoWhite({
  className,
  height = 32,
  href = "/",
}: Omit<GravitreMarketingLogoProps, "priority">) {
  return wrap(<GravitreMark size={height} className={className} />, href)
}
