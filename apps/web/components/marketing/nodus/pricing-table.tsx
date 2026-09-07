"use client"

import React, { useMemo } from "react"
import Link from "next/link"
import { Container } from "./container"
import { Button } from "./button"
import { SlidingNumber } from "./sliding-number"
import { cn } from "@/lib/utils"
import { CheckIcon } from "@/components/marketing/nodus-icons/card-icons"
import { usePricingAnnual } from "@/components/marketing/pricing/pricing-annual-context"
import {
  aiCapabilityRows,
  tiers,
  type PlanComparisonCell,
} from "@/lib/pricing-page-data"
import { SHOW_RESEARCH_LOOKUPS_PRICING } from "@/lib/marketing-flags"
import { MARKETING_COPY } from "@/lib/marketing-copy"

type TableRow = {
  title: string
  node: PlanComparisonCell
  control: PlanComparisonCell
  command: PlanComparisonCell
}

const usageRows: TableRow[] = [
  { title: "Monthly outputs", node: "10", control: "40", command: "120" },
  ...(SHOW_RESEARCH_LOOKUPS_PRICING
    ? [{ title: "Research lookups", node: "10", control: "60", command: "200" } satisfies TableRow]
    : []),
  { title: "AI Agents", node: "1", control: "2–3", command: "5–8" },
  { title: "Core Users", node: "1", control: "2", command: "5" },
  { title: "Lite Users", node: "2", control: "5", command: "Unlimited" },
  { title: "Mesons / month", node: "—", control: "10", command: "40" },
]

const deliveryRows: TableRow[] = [
  { title: "Email delivery", node: true, control: true, command: true },
  { title: "Slack delivery", node: false, control: true, command: true },
  { title: "CRM + Outlook integrations", node: false, control: true, command: true },
  { title: "Advanced integrations", node: false, control: false, command: true },
]

const supportRows: TableRow[] = [
  { title: "Community support", node: true, control: true, command: true },
  { title: "Priority support", node: false, control: true, command: true },
  { title: "Dedicated support", node: false, control: false, command: true },
  { title: "Team collaboration workspace", node: false, control: false, command: true },
  { title: "Approvals + workflows", node: false, control: false, command: true },
]

/**
 * Nodus comparison matrix — values from authorized Gravitre plan data only.
 */
export function PricingTable() {
  const { isAnnual, setIsAnnual } = usePricingAnnual()
  const cycle = isAnnual ? "yearly" : "monthly"

  const titleToPrice = useMemo(() => {
    const map: Record<string, { monthly: number; yearly: number }> = {}
    for (const t of tiers) {
      map[t.name] = { monthly: t.price.monthly, yearly: t.price.annual }
    }
    return map
  }, [])

  const ordered = tiers.map((t) => t.name)

  const sections: { label: string; rows: TableRow[] }[] = [
    { label: "Usage & limits", rows: usageRows },
    { label: "AI capabilities", rows: aiCapabilityRows.map((r) => ({ title: r.feature, node: r.node, control: r.control, command: r.command })) },
    { label: "Integrations & delivery", rows: deliveryRows },
    { label: "Support & collaboration", rows: supportRows },
  ]

  return (
    <section>
      <Container className="border-divide border-x px-4 py-10 md:px-8">
        <p className="text-brand text-center text-sm font-normal">Compare plans</p>
        <h2 className="text-charcoal-700 mt-2 text-center text-2xl font-medium tracking-tight md:text-3xl dark:text-neutral-100">
          Compare all features
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-center text-sm text-gray-600 dark:text-neutral-400">
          {MARKETING_COPY.pricing.comparisonIntro}
        </p>
      </Container>

      <Container className="border-divide border-x">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left">
            <thead>
              <tr className="border-divide divide-divide divide-x border-b">
                <th className="min-w-[200px] px-4 pt-10 pb-8 align-bottom text-sm font-medium text-gray-600 dark:text-neutral-200">
                  <div className="mb-2 text-sm font-normal text-gray-600 dark:text-neutral-200">
                    Select a preferred cycle
                  </div>
                  <div className="inline-flex rounded-md bg-gray-100 p-1 dark:bg-neutral-800">
                    {(
                      [
                        { label: "Monthly", value: "monthly" as const },
                        { label: "Yearly", value: "yearly" as const },
                      ] as const
                    ).map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => setIsAnnual(opt.value === "yearly")}
                        className={cn(
                          "relative z-10 rounded-md px-3 py-1 text-sm text-gray-800 dark:text-white",
                          cycle === opt.value &&
                            "shadow-aceternity bg-white dark:bg-neutral-900 dark:text-white",
                        )}
                        aria-pressed={cycle === opt.value}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </th>
                {ordered.map((name) => {
                  const tier = tiers.find((t) => t.name === name)!
                  return (
                    <th key={`hdr-${name}`} className="min-w-[180px] px-4 pt-10 pb-8 align-bottom">
                      <div className="text-charcoal-700 text-lg font-medium dark:text-neutral-100">{name}</div>
                      <div className="mt-1 flex items-center text-sm font-normal text-gray-600 dark:text-neutral-300">
                        $<SlidingNumber value={titleToPrice[name]?.[cycle === "yearly" ? "yearly" : "monthly"]} />
                        /month billed {cycle === "monthly" ? "monthly" : "annually"}
                      </div>
                      <Button
                        as={Link}
                        href={`/get-started?plan=${tier.planCode}&interval=${isAnnual ? "annual" : "monthly"}`}
                        className="mt-4 w-full"
                        variant={tier.highlighted ? "brand" : "secondary"}
                      >
                        {tier.cta}
                      </Button>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {sections.map((section) => (
                <React.Fragment key={section.label}>
                  <tr className="border-divide border-b bg-gray-50 dark:bg-neutral-900">
                    <td
                      colSpan={4}
                      className="text-charcoal-700 px-4 py-3 text-xs font-semibold tracking-wider uppercase dark:text-neutral-300"
                    >
                      {section.label}
                    </td>
                  </tr>
                  {section.rows.map((row, index) => (
                    <tr
                      key={row.title}
                      className={cn(
                        "border-divide divide-divide divide-x border-b",
                        index % 2 === 0 && "bg-gray-50/70 dark:bg-neutral-800/40",
                      )}
                    >
                      <td className="text-charcoal-700 px-4 py-5 text-sm dark:text-neutral-100">{row.title}</td>
                      {(["node", "control", "command"] as const).map((key) => (
                        <td
                          key={`${row.title}-${key}`}
                          className="text-charcoal-700 px-4 py-5 text-center text-sm dark:text-neutral-100"
                        >
                          <CellValue value={row[key]} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Container>
    </section>
  )
}

function CellValue({ value }: { value: PlanComparisonCell }) {
  if (typeof value === "boolean") {
    return value ? (
      <span className="inline-flex items-center justify-center">
        <CheckIcon className="h-4 w-4" />
      </span>
    ) : (
      <span className="text-gray-400 dark:text-neutral-600">—</span>
    )
  }
  return <span>{value}</span>
}

export default PricingTable
