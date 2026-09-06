"use client"

import { motion } from "framer-motion"
import {
  NucleoAgent,
  NucleoApproval,
  NucleoIntelligence,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { GibeHonestyCards } from "@/components/marketing/gibe-honesty-cards"

export function ConnectorsStepVisual() {
  return (
    <div className="rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-6 shadow-[var(--g-shadow-elevated)]">
      <div className="space-y-3">
        {[
          { label: "HubSpot", status: "Executable", ok: true },
          { label: "Salesforce", status: "Auth required", ok: false },
          { label: "Slack", status: "Healthy", ok: true },
        ].map((row, i) => (
          <motion.div
            key={row.label}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center justify-between rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] p-4"
          >
            <span className="text-sm text-foreground">{row.label}</span>
            <span
              className={`rounded-full px-2 py-1 text-xs ${
                row.ok
                  ? "bg-primary/15 text-primary"
                  : "border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] text-muted-foreground"
              }`}
            >
              {row.status}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

export function GibeHonestyStepVisual() {
  return (
    <div className="rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-6 shadow-[var(--g-shadow-elevated)]">
      <GibeHonestyCards />
    </div>
  )
}

export function AgentsStepVisual() {
  return (
    <div className="rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-6 shadow-[var(--g-shadow-elevated)]">
      <div className="flex items-center justify-center gap-2">
        {[
          { icon: NucleoWorkflow, tone: "emerald" as const },
          { icon: NucleoAgent, tone: "signal" as const },
          { icon: NucleoIntelligence, tone: "intelligence" as const },
          { icon: NucleoApproval, tone: "emerald" as const },
        ].map((node, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center"
          >
            <div
              className={`flex h-12 w-12 items-center justify-center rounded-xl border ${
                node.tone === "emerald"
                  ? "border-primary/30 bg-primary/10"
                  : node.tone === "signal"
                    ? "border-[color:var(--g-signal)]/30 bg-[color:var(--g-signal)]/10"
                    : "border-[color:var(--g-intelligence)]/30 bg-[color:var(--g-intelligence)]/10"
              }`}
            >
              <node.icon
                size={20}
                className={
                  node.tone === "emerald"
                    ? "text-primary"
                    : node.tone === "signal"
                      ? "text-[color:var(--g-signal)]"
                      : "text-[color:var(--g-intelligence)]"
                }
              />
            </div>
            {i < 3 ? <div className="h-0.5 w-6 bg-muted" /> : null}
          </motion.div>
        ))}
      </div>
    </div>
  )
}
