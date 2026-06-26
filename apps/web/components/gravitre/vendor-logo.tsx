"use client"

import { ConnectorIcon, type ConnectorIconSize } from "@/components/gravitre/connector-icon"
import { cn } from "@/lib/utils"

interface VendorLogoProps {
  vendor: string
  size?: "sm" | "md" | "lg"
  variant?: "default" | "light"
  className?: string
}

const sizeMap: Record<NonNullable<VendorLogoProps["size"]>, ConnectorIconSize> = {
  sm: "xs",
  md: "sm",
  lg: "md",
}

/** @deprecated Use ConnectorIcon directly — kept for legacy call sites. */
export function VendorLogo({
  vendor,
  size = "md",
  variant = "default",
  className,
}: VendorLogoProps) {
  return (
    <ConnectorIcon
      vendor={vendor}
      size={sizeMap[size]}
      showStatusIndicator={false}
      forceLight
      className={cn(className)}
    />
  )
}
