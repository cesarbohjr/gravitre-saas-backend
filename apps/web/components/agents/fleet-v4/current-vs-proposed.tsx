"use client"

import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { resolveAgentIdentity } from "@/lib/agent-identity"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { FLEET_FIXTURE_AGENTS } from "./fixtures"

/** Side-by-side: current glow orbs vs proposed compact tiles. */
export function CurrentVsProposed() {
  const sample = FLEET_FIXTURE_AGENTS.slice(0, 4)

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="space-y-3 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wide text-rose-700 dark:text-rose-300">
            Current
          </p>
          <h3 className="text-sm font-semibold">Glow orb constellation</h3>
          <p className="text-xs text-[color:var(--g-text-muted)]">
            Large circular gradients + Lucide glyphs + personality glow.
          </p>
        </div>
        <div className="relative flex flex-wrap items-center justify-center gap-6 overflow-hidden py-8">
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-[220px] w-[220px] rounded-full border border-chart-4/10" />
            <div className="absolute h-[150px] w-[150px] rounded-full border border-chart-2/10" />
          </div>
          {sample.map((a) => {
            const identity = resolveAgentIdentity({
              name: a.name,
              role: a.role,
              icon: a.icon === "sales" ? "trending-up" : a.icon === "finance" ? "pie-chart" : "brain",
              avatarColor:
                a.identityColor === "green"
                  ? "bg-emerald-500"
                  : a.identityColor === "violet"
                    ? "bg-purple-500"
                    : a.identityColor === "cyan"
                      ? "bg-cyan-500"
                      : "bg-blue-500",
            })
            return (
              <div key={a.id} className="relative z-10 flex w-[120px] flex-col items-center gap-2">
                <div className="relative">
                  <div
                    className={`absolute inset-0 scale-125 rounded-full bg-gradient-to-br opacity-30 blur-2xl ${identity.personality.gradient}`}
                  />
                  <AgentIdentityAvatar identity={identity} size="orb" />
                </div>
                <p className="line-clamp-2 text-center text-[11px] font-medium">{a.name}</p>
              </div>
            )
          })}
        </div>
      </section>

      <section className="space-y-3 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
            Proposed
          </p>
          <h3 className="text-sm font-semibold">Compact symbol tiles</h3>
          <p className="text-xs text-[color:var(--g-text-muted)]">
            Nucleo / Nodus icons, pale surfaces, status as dots — not avatar recolor.
          </p>
        </div>
        <div className="grid gap-3 py-4 sm:grid-cols-2">
          {sample.map((a) => (
            <div
              key={a.id}
              className="flex items-center gap-3 rounded-[var(--np-radius-md)] border border-divide px-3 py-2.5"
            >
              <GravitreAgentIdentity
                icon={a.icon}
                identityColor={a.identityColor}
                status={a.runtimeState}
                variant="card"
              />
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{a.name}</p>
                <p className="truncate text-xs text-[color:var(--g-text-muted)]">{a.role}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
