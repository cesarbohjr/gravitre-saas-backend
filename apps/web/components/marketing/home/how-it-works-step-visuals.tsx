"use client"

import { motion } from "framer-motion"
import { Bot, Shield, Users, Zap } from "lucide-react"
import { GibeHonestyCards } from "@/components/marketing/gibe-honesty-cards"

export function ConnectorsStepVisual() {
  return (
    <div className="bg-foreground rounded-xl p-6 shadow-2xl border border-zinc-800">
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
            className="flex items-center justify-between p-4 rounded-lg border border-zinc-800 bg-foreground/90/50"
          >
            <span className="text-sm text-zinc-200">{row.label}</span>
            <span
              className={`text-xs px-2 py-1 rounded-full ${
                row.ok ? "bg-primary/100/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
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
    <div className="bg-foreground rounded-xl p-6 shadow-2xl border border-zinc-800">
      <GibeHonestyCards />
    </div>
  )
}

export function AgentsStepVisual() {
  return (
    <div className="bg-foreground rounded-xl p-6 shadow-2xl border border-zinc-800">
      <div className="flex items-center justify-center gap-2">
        {[
          { icon: Zap, color: "emerald" },
          { icon: Bot, color: "blue" },
          { icon: Users, color: "purple" },
          { icon: Shield, color: "amber" },
        ].map((node, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center"
          >
            <div
              className={`h-12 w-12 rounded-xl flex items-center justify-center border ${
                node.color === "emerald"
                  ? "border-primary/30 bg-primary/100/10"
                  : node.color === "blue"
                    ? "border-blue-500/30 bg-blue-500/10"
                    : node.color === "purple"
                      ? "border-purple-500/30 bg-purple-500/10"
                      : "border-amber-500/30 bg-amber-500/10"
              }`}
            >
              <node.icon
                className={`h-5 w-5 ${
                  node.color === "emerald"
                    ? "text-emerald-400"
                    : node.color === "blue"
                      ? "text-blue-400"
                      : node.color === "purple"
                        ? "text-purple-400"
                        : "text-amber-400"
                }`}
              />
            </div>
            {i < 3 && <div className="w-6 h-0.5 bg-zinc-700" />}
          </motion.div>
        ))}
      </div>
    </div>
  )
}
