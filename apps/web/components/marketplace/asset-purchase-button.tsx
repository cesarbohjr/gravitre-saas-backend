"use client"

import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { marketplaceApi } from "@/lib/api"
import { Loader2, ShoppingCart } from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetInstallCheck,
  MarketplaceAssetSummary,
} from "@/types/api"

function formatPrice(cents?: number, currency = "usd") {
  if (cents == null || !Number.isSafeInteger(cents) || cents <= 0)
    return "Price not reported"
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format((cents ?? 0) / 100)
}

export function AssetPurchaseButton({
  asset,
  check,
  onPurchased,
  className,
}: {
  asset: MarketplaceAssetSummary
  check: MarketplaceAssetInstallCheck
  onPurchased: () => void
  className?: string
}) {
  const lock = useRef(false)
  const [busy, setBusy] = useState(false)
  const runCheckout = async () => {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    try {
      const origin = window.location.origin
      const result = await marketplaceApi.assetCheckout(asset.slug, {
        successUrl: `${origin}/marketplace/assets/${encodeURIComponent(asset.slug)}?purchase=success`,
        cancelUrl: `${origin}/marketplace/assets/${encodeURIComponent(asset.slug)}?purchase=cancelled`,
      })
      if (result.checkoutUrl) {
        window.location.href = result.checkoutUrl
        return
      }
      onPurchased()
    } catch (err) {
      toast.error("Checkout failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  return (
    <Button
      className={className ?? "w-full"}
      disabled={busy}
      onClick={() => void runCheckout()}
    >
      {busy ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <ShoppingCart className="mr-2 h-4 w-4" aria-hidden />
      )}
      Purchase {formatPrice(check.priceCents, check.currency)} to unlock install
    </Button>
  )
}
