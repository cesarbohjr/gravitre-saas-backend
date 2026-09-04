"use client"

import Link from "next/link"
import {
  ArrowRight,
  Blocks,
  Check,
  Cpu,
  Globe,
  Monitor,
  Smartphone,
  X,
} from "lucide-react"
import { SHOW_RESEARCH_LOOKUPS_PRICING } from "@/lib/marketing-flags"
import { researchLookupsIncludedLabel } from "@/lib/internet-research-pricing"
import { tiers, type PricingTier } from "@/lib/pricing-page-data"
import { usePricingAnnual } from "./pricing-annual-context"
import { PricingRoleTooltip } from "./pricing-role-tooltip"

function PricingCard({ tier, isAnnual }: { tier: PricingTier; isAnnual: boolean }) {
  const price = isAnnual ? tier.price.annual : tier.price.monthly
  const TierIcon = tier.icon

  return (
    <div className="group relative">
      {tier.highlighted && (
        <div className={`absolute -inset-px rounded-3xl bg-gradient-to-b ${tier.gradient} blur-xl opacity-20 group-hover:opacity-30 transition-opacity`} />
      )}

      <div
        className={`relative h-full rounded-2xl sm:rounded-3xl border p-5 sm:p-8 transition-all ${
          tier.highlighted
            ? "border-amber-300 bg-amber-50/50 shadow-lg"
            : "border-border bg-card hover:border-border hover:shadow-md"
        }`}
      >
        {"badge" in tier && tier.badge ? (
          <div className="absolute -top-4 left-1/2 -translate-x-1/2">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r ${tier.gradient} px-4 py-1.5 text-xs font-semibold text-white shadow-lg`}
            >
              {tier.badge}
            </span>
          </div>
        ) : null}

        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className={`h-8 w-8 rounded-lg bg-gradient-to-r ${tier.gradient} flex items-center justify-center`}>
              <TierIcon className="h-4 w-4 text-white" />
            </div>
            <h3 className="text-xl font-semibold text-foreground">{tier.name}</h3>
          </div>
          <p className="text-sm text-muted-foreground">{tier.tagline}</p>
        </div>

        <div className="mb-5 sm:mb-6">
          <div className="flex items-baseline gap-1">
            <span className="text-4xl sm:text-5xl font-bold text-foreground">${price}</span>
            <span className="text-muted-foreground text-sm sm:text-base">/month</span>
          </div>
          {isAnnual && (
            <p className="mt-1 text-xs text-primary">
              Billed annually (save ${(tier.price.monthly - tier.price.annual) * 12}/year)
            </p>
          )}
        </div>

        <div className="mb-6 p-4 rounded-2xl bg-muted/50 border border-border">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">Team Structure</p>
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground flex items-center gap-2">
                <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                Agents
              </span>
              <span className="text-sm font-medium text-foreground">{tier.team.agents}</span>
            </div>
            <div className="flex items-center justify-between">
              <PricingRoleTooltip role="coreUser">
                <span className="text-sm text-muted-foreground flex items-center gap-2">
                  <Monitor className="h-3.5 w-3.5 text-muted-foreground" />
                  Core Users
                </span>
              </PricingRoleTooltip>
              <span className="text-sm font-medium text-foreground">{tier.team.coreUsers}</span>
            </div>
            <div className="flex items-center justify-between">
              <PricingRoleTooltip role="liteUser">
                <span className="text-sm text-muted-foreground flex items-center gap-2">
                  <Smartphone className="h-3.5 w-3.5 text-muted-foreground" />
                  Lite Users
                </span>
              </PricingRoleTooltip>
              <span className="text-sm font-medium text-foreground">{tier.team.liteUsers}</span>
            </div>
          </div>
        </div>

        <div
          className="mb-4 p-4 rounded-2xl"
          style={{
            background: `linear-gradient(to right, rgb(${tier.color === "emerald" ? "16 185 129" : tier.color === "amber" ? "245 158 11" : "59 130 246"} / 0.1), transparent)`,
          }}
        >
          <div className="flex items-center gap-2">
            <div className={`h-2 w-2 rounded-full bg-gradient-to-r ${tier.gradient}`} />
            <span className="text-sm font-semibold text-foreground">{tier.outputs}</span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Campaigns, email sequences, reports, workflows</p>
        </div>

        <div
          className={`mb-6 p-4 rounded-2xl border ${tier.meson ? "border-violet-200 bg-violet-50" : "border-border bg-muted/50"}`}
        >
          <div className="flex items-center gap-2 mb-2">
            <Blocks className={`h-4 w-4 ${tier.meson ? "text-violet-600" : "text-muted-foreground"}`} />
            <span
              className={`text-xs font-semibold uppercase tracking-wider ${tier.meson ? "text-violet-600" : "text-muted-foreground"}`}
            >
              Meson
            </span>
          </div>
          {tier.meson ? (
            <>
              <p className="text-sm font-medium text-foreground">{tier.meson.label}</p>
              <p className="mt-1 text-xs text-muted-foreground">Build systems from a single request</p>
            </>
          ) : (
            <>
              <p className="text-sm text-muted-foreground flex items-center gap-2">
                <X className="h-3.5 w-3.5" />
                Not included
              </p>
              <p className="mt-1 text-xs text-muted-foreground">Upgrade to Control for Meson access</p>
            </>
          )}
        </div>

        {SHOW_RESEARCH_LOOKUPS_PRICING && researchLookupsIncludedLabel(tier.planCode) ? (
          <div className="mb-6 p-4 rounded-2xl border border-sky-200 bg-sky-50">
            <div className="flex items-center gap-2 mb-2">
              <Globe className="h-4 w-4 text-sky-600" />
              <span className="text-xs font-semibold uppercase tracking-wider text-sky-600">
                Research Lookups
              </span>
            </div>
            <p className="text-sm font-medium text-foreground">{researchLookupsIncludedLabel(tier.planCode)}</p>
            <p className="mt-1 text-xs text-muted-foreground">Live internet research when enabled for your workspace</p>
          </div>
        ) : null}

        <ul className="mb-8 space-y-3">
          {tier.features.map((feature) => (
            <li key={feature} className="flex items-start gap-3">
              <div
                className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
                  tier.highlighted ? "bg-amber-100" : "bg-muted"
                }`}
              >
                <Check className={`h-3 w-3 ${tier.highlighted ? "text-amber-600" : "text-muted-foreground"}`} />
              </div>
              <span className="text-sm text-muted-foreground">{feature}</span>
            </li>
          ))}
        </ul>

        <Link
          href={`/get-started?plan=${tier.planCode}&interval=${isAnnual ? "annual" : "monthly"}`}
          className={`group/btn inline-flex w-full items-center justify-center gap-2 rounded-full px-6 py-3.5 text-sm font-semibold transition-all ${
            tier.highlighted
              ? "bg-foreground text-white hover:bg-foreground/90 shadow-lg shadow-foreground/20"
              : "border border-border bg-card text-foreground hover:bg-muted/50 hover:border-border"
          }`}
        >
          {tier.cta}
          <ArrowRight className="h-4 w-4 transition-transform group-hover/btn:translate-x-1" />
        </Link>
      </div>
    </div>
  )
}

export function PricingCardsGrid() {
  const { isAnnual } = usePricingAnnual()

  return (
    <div className="grid gap-4 sm:gap-8 lg:grid-cols-3">
      {tiers.map((tier) => (
        <PricingCard key={tier.name} tier={tier} isAnnual={isAnnual} />
      ))}
    </div>
  )
}
