"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import useSWR from "swr"
import { accountIntelligenceApi } from "@/lib/api"
import { CONTEXT_HELP_HREF, CUSTOMER_DATA_SETTINGS_HREF } from "@/lib/context-sources"

/** Same key as Settings › Customer data, so both share one cache entry. */
const GOVERNANCE_KEY = "/api/settings/source-governance"

export type CustomerContextState = "on" | "off" | "unknown"

/** Whether this workspace switched customer context on. "unknown" while loading or on error. */
export function useCustomerContextState(): CustomerContextState {
  const { data, error } = useSWR(GOVERNANCE_KEY, () => accountIntelligenceApi.sourceGovernance(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })
  if (error || !data?.sourceDataGovernance) return "unknown"
  return data.sourceDataGovernance.customerContext.enabled ? "on" : "off"
}

function TurnOnLink() {
  return (
    <>
      Turn on customer context in{" "}
      <Link href={CUSTOMER_DATA_SETTINGS_HREF} className="text-foreground underline underline-offset-2">
        Settings › Customer data
      </Link>
      .
    </>
  )
}

/**
 * Honest copy for a customer-context surface that has nothing to show.
 *
 * - `notAvailable`: the feature isn't switched on for this workspace yet (the
 *   route answered 404). Say what it would show; the opt-in is still needed.
 * - `empty`: the feature is on but returned nothing. Say whether that is
 *   because customer context is off, or because there is no data yet.
 */
export function CustomerContextOffState({
  feature,
  whatItShows,
  reason,
  emptyMessage,
}: {
  feature: string
  whatItShows: string
  reason: "notAvailable" | "empty"
  /** Shown when customer context is on and there is simply no data yet. */
  emptyMessage: string
}) {
  const state = useCustomerContextState()
  let message: ReactNode
  if (reason === "notAvailable") {
    message = (
      <>
        {feature} isn&apos;t switched on for your workspace yet. When it is, it will show {whatItShows}{" "}
        {state === "on" ? "Customer context is already on, so it will start from your connected systems." : <TurnOnLink />}
      </>
    )
  } else if (state === "off") {
    message = (
      <>
        {feature} shows {whatItShows} Nothing is read until you allow it. <TurnOnLink />
      </>
    )
  } else {
    message = state === "on" ? <>Customer context is on. {emptyMessage}</> : <>{emptyMessage}</>
  }
  return (
    <div className="space-y-1 text-sm text-muted-foreground" data-testid="customer-context-off-state">
      <p>{message}</p>
      <p className="text-xs">
        <Link href={CONTEXT_HELP_HREF} className="underline underline-offset-2 hover:text-foreground">
          How Gravitre uses your context
        </Link>
      </p>
    </div>
  )
}
