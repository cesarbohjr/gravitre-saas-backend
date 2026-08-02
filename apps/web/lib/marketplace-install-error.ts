import { toast } from "sonner"

export type PlanLimitDetail = {
  limitType: string
  current: number
  max: number
  upgradeUrl?: string
}

function detailObject(payload: unknown): Record<string, unknown> | null {
  if (!payload || typeof payload !== "object") return null
  const data = payload as Record<string, unknown>
  const detail = data.detail
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    return detail as Record<string, unknown>
  }
  return null
}

export function parsePlanLimitDetail(err: unknown): PlanLimitDetail | null {
  const payload =
    err && typeof err === "object" && "payload" in err
      ? (err as { payload: unknown }).payload
      : null
  const detail = detailObject(payload)
  if (!detail) return null
  if (detail.error !== "plan_limit_exceeded" && detail.code !== "LIMIT_EXCEEDED") return null
  const limitType = String(detail.limit_type ?? detail.limitType ?? "plan")
  const current = Number(detail.current ?? 0)
  const max = Number(detail.max ?? 0)
  const upgradeUrl =
    typeof detail.upgrade_url === "string"
      ? detail.upgrade_url
      : typeof detail.upgradeUrl === "string"
        ? detail.upgradeUrl
        : undefined
  return { limitType, current, max, upgradeUrl }
}

export function parsePaymentRequiredDetail(err: unknown): { priceCents?: number; currency?: string } | null {
  const payload =
    err && typeof err === "object" && "payload" in err
      ? (err as { payload: unknown }).payload
      : null
  const detail = detailObject(payload)
  if (!detail) return null
  if (detail.code !== "PAYMENT_REQUIRED" && detail.error !== "PAYMENT_REQUIRED") return null
  const nested = detail.details && typeof detail.details === "object" ? (detail.details as Record<string, unknown>) : detail
  return {
    priceCents: Number(nested.priceCents ?? nested.price_cents ?? 0) || undefined,
    currency: typeof nested.currency === "string" ? nested.currency : undefined,
  }
}

export function toastMarketplaceInstallFailure(
  err: unknown,
  options?: { blockerActionUrl?: string | null },
): void {
  const limit = parsePlanLimitDetail(err)
  if (limit) {
    toast.error("Plan limit reached", {
      description: `${limit.limitType} usage is ${limit.current} of ${limit.max}. Upgrade your plan to install more assets.`,
      action: limit.upgradeUrl
        ? {
            label: "Upgrade",
            onClick: () => {
              window.location.href = limit.upgradeUrl!
            },
          }
        : undefined,
    })
    return
  }

  const payment = parsePaymentRequiredDetail(err)
  if (payment) {
    toast.error("Purchase required", {
      description: "Complete checkout for this asset before installing.",
    })
    return
  }

  const payload =
    err && typeof err === "object" && "payload" in err
      ? (err as { payload: unknown }).payload
      : null
  const detail = detailObject(payload)
  const code =
    (detail && typeof detail.code === "string" && detail.code) ||
    (payload &&
      typeof payload === "object" &&
      typeof (payload as { code?: unknown }).code === "string" &&
      String((payload as { code: string }).code)) ||
    null

  const message = err instanceof Error ? err.message : "Install failed"
  const isGenericInternal =
    /unexpected error occurred/i.test(message) || code === "INTERNAL_ERROR"

  toast.error(/connect required apps/i.test(message) ? "Connect required apps first" : "Install failed", {
    description: isGenericInternal
      ? "The install could not finish. Check Agents / Workflows for a partial install, then retry. If it keeps failing, contact support with the asset name."
      : message,
    action: options?.blockerActionUrl
      ? {
          label: "Connect apps",
          onClick: () => {
            window.location.href = options.blockerActionUrl!
          },
        }
      : undefined,
  })
}
