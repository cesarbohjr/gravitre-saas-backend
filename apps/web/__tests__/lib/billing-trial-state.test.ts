import { describe, expect, it } from "vitest"
import {
  isBillingStatusDegraded,
  isTrialExpiredFromBillingStatus,
  isTrialExpiredFromPlanRequired,
  isTrialExpiredState,
  resolveCanAccessApp,
} from "@/lib/billing-trial-state"
import type { PlanRequiredDetail } from "@/lib/billing-plan-required"

describe("billing trial state", () => {
  it("detects trial expiry from billing status", () => {
    expect(
      isTrialExpiredFromBillingStatus({
        trialExpired: true,
        canAccessApp: false,
        billingKnown: true,
      }),
    ).toBe(true)
  })

  it("ignores degraded billing status", () => {
    expect(
      isTrialExpiredFromBillingStatus({
        trialExpired: true,
        billingKnown: false,
        _auth_degraded: true,
      }),
    ).toBe(false)
  })

  it("detects trial expiry from stored 402 payload", () => {
    const detail: PlanRequiredDetail = {
      error: "plan_required",
      subscription_status: "trial_expired",
    }
    expect(isTrialExpiredFromPlanRequired(detail)).toBe(true)
    expect(isTrialExpiredState(undefined, detail)).toBe(true)
  })

  it("does not clear trial state when billing is degraded", () => {
    expect(
      resolveCanAccessApp(
        { billingKnown: false, _auth_degraded: true, canAccessApp: null },
        null,
        { error: "plan_required", subscription_status: "trial_expired" },
      ),
    ).toBe(false)
  })

  it("grants access only when billing explicitly allows it", () => {
    expect(
      resolveCanAccessApp(
        { canAccessApp: true, billingKnown: true },
        null,
        null,
      ),
    ).toBe(true)
    expect(isBillingStatusDegraded({ billingKnown: false, _auth_degraded: true })).toBe(true)
  })
})
