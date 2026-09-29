"use client"

import { ProviderLogo } from "@/components/gravitre/provider-logo"

interface VendorLogoProps {
  vendor: string
  size?: "sm" | "md" | "lg"
  variant?: "default" | "light"
  className?: string
}

/** @deprecated Use ProviderLogo directly — kept for legacy call sites. */
export function VendorLogo({ vendor, size = "md", variant = "default", className }: VendorLogoProps) {
  return <ProviderLogo provider={vendor} size={size} theme={variant === "light" ? "light" : "auto"} className={className} />
}
