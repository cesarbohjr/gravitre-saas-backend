import Image from "next/image"
import Link from "next/link"
import { cn } from "@/lib/utils"

type GravitreMarketingLogoProps = {
  className?: string
  height?: number
  href?: string
  priority?: boolean
}

export function GravitreMarketingLogo({
  className,
  height = 40,
  href = "/",
  priority = false,
}: GravitreMarketingLogoProps) {
  const width = Math.round(height * 4.5)

  const image = (
    <>
      <Image
        src="/images/gravitre-logo-black.png"
        alt="Gravitre"
        width={width}
        height={height}
        priority={priority}
        className={cn("h-auto w-auto dark:hidden", className)}
      />
      <Image
        src="/images/gravitre-logo-white.png"
        alt="Gravitre"
        width={width}
        height={height}
        priority={priority}
        className={cn("hidden h-auto w-auto dark:block", className)}
      />
    </>
  )

  if (!href) return <span className="inline-flex items-center">{image}</span>

  return (
    <Link href={href} className="inline-flex items-center">
      {image}
    </Link>
  )
}

export function GravitreMarketingLogoWhite({
  className,
  height = 32,
  href = "/",
}: Omit<GravitreMarketingLogoProps, "priority">) {
  const width = Math.round(height * 4.5)
  const image = (
    <Image
      src="/logo-white.svg"
      alt="Gravitre"
      width={width}
      height={height}
      className={cn("h-auto w-auto", className)}
    />
  )

  if (!href) return <span className="inline-flex items-center">{image}</span>

  return (
    <Link href={href} className="inline-flex items-center">
      {image}
    </Link>
  )
}
