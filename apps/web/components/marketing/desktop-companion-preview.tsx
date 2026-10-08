"use client"

import { motion, useScroll, useTransform } from "framer-motion"
import { Check, Keyboard, MessageSquare, Shield, Sparkles } from "lucide-react"
import { useRef } from "react"

/**
 * Marketing mock of the desktop companion window — chat / activity / approvals.
 * Structural UI only; no invented metrics or prices.
 */
export function DesktopCompanionPreview() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  })
  const y = useTransform(scrollYProgress, [0, 1], [48, -48])
  const opacity = useTransform(scrollYProgress, [0, 0.2, 0.85, 1], [0, 1, 1, 0.85])

  return (
    <motion.div ref={ref} style={{ y, opacity }} className="relative mx-auto max-w-4xl">
      <div className="pointer-events-none absolute -inset-6 rounded-[2rem] bg-gradient-to-b from-[color:var(--g-emerald)]/20 via-transparent to-transparent blur-2xl" />

      {/* Floating accent chips */}
      <motion.div
        className="absolute -left-2 top-10 z-10 hidden rounded-2xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]/95 px-3 py-2 shadow-[var(--g-shadow-elevated)] backdrop-blur sm:flex sm:items-center sm:gap-2 lg:-left-8"
        animate={{ y: [0, -8, 0] }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
      >
        <Keyboard className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground">Alt+Space</span>
      </motion.div>
      <motion.div
        className="absolute -right-2 top-24 z-10 hidden rounded-2xl border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]/95 px-3 py-2 shadow-[var(--g-shadow-elevated)] backdrop-blur sm:flex sm:items-center sm:gap-2 lg:-right-6"
        animate={{ y: [0, 10, 0] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 0.8 }}
      >
        <Shield className="h-4 w-4 text-primary" />
        <span className="text-xs font-semibold text-foreground">Approve writes</span>
      </motion.div>

      <div
        className="relative overflow-hidden rounded-[1.35rem] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-2 shadow-[0_28px_80px_-36px_rgba(0,0,0,0.65)]"
        style={{
          maskImage:
            "linear-gradient(to bottom, black 0%, black 78%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to bottom, black 0%, black 78%, transparent 100%)",
        }}
      >
        {/* Title bar — graphite chrome, no yellow traffic light */}
        <div className="flex items-center gap-2 rounded-t-[1.05rem] border-b border-border bg-muted/50 px-4 py-3">
          <div className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full bg-muted-foreground/40" />
            <span className="h-3 w-3 rounded-full bg-muted-foreground/28" />
            <span className="h-3 w-3 rounded-full bg-primary/55" />
          </div>
          <div className="flex-1 text-center">
            <span className="text-xs font-medium text-muted-foreground">Gravitre Desktop</span>
          </div>
          <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
            Connected
          </span>
        </div>

        {/* Dark companion shell (matches apps/desktop) */}
        <div className="overflow-hidden rounded-b-[1.05rem] bg-background text-foreground">
          <div className="flex items-center gap-2 border-b border-border bg-card px-4 py-2.5">
            <span className="text-sm font-semibold tracking-tight">Gravitre</span>
            <span className="ml-auto rounded-full border border-brand/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-brand-text">
              Online
            </span>
          </div>

          <div className="flex gap-1 border-b border-border px-3 py-2">
            {(
              [
                { id: "chat", label: "Chat", active: true, Icon: MessageSquare },
                { id: "activity", label: "Activity", active: false, Icon: Sparkles },
                { id: "approvals", label: "Approvals", active: false, Icon: Shield },
              ] as const
            ).map(({ id, label, active, Icon }) => (
              <div
                key={id}
                className={[
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium",
                  active
                    ? "bg-brand/20 text-foreground"
                    : "text-muted-foreground",
                ].join(" ")}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </div>
            ))}
          </div>

          <div className="grid gap-0 sm:grid-cols-[1.15fr_0.85fr]">
            <div className="flex min-h-[280px] flex-col p-4 sm:min-h-[320px]">
              <div className="mb-3 inline-flex w-fit gap-1 rounded-full border border-border bg-card p-0.5">
                <span className="rounded-full bg-brand px-2.5 py-0.5 text-[10px] font-semibold text-brand-foreground">
                  Text
                </span>
                <span className="rounded-full px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                  Voice
                </span>
              </div>

              <div className="flex-1 space-y-3">
                <motion.div
                  className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-info px-3.5 py-2.5 text-sm leading-relaxed text-info-foreground"
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.15 }}
                >
                  Summarize pending approvals and draft a reply.
                </motion.div>
                <motion.div
                  className="max-w-[90%] rounded-2xl rounded-bl-md border border-border bg-card px-3.5 py-2.5 text-sm leading-relaxed text-foreground"
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.35 }}
                >
                  Two writes waiting. Approve from here — Outcomes stays in sync on the web.
                </motion.div>
                <p className="pt-1 text-[11px] text-muted-foreground">
                  Summon anytime with Alt+Space · Option+Space on Mac
                </p>
              </div>

              <div className="mt-4 flex items-end gap-2 rounded-xl border border-border bg-card p-2">
                <div className="min-h-[40px] flex-1 rounded-lg px-2 py-2 text-sm text-muted-foreground">
                  Message Gravitre…
                </div>
                <div className="rounded-lg bg-brand px-3 py-2 text-xs font-semibold text-brand-foreground">
                  Send
                </div>
              </div>
            </div>

            <div className="border-t border-border bg-muted p-4 sm:border-l sm:border-t-0">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Needs approval
              </p>
              <div className="space-y-3">
                {[
                  {
                    title: "Create HubSpot note",
                    summary: "Write waits for your confirm before it runs.",
                  },
                  {
                    title: "Update Apollo contact",
                    summary: "Catalog write — not a browser click.",
                  },
                ].map((item, i) => (
                  <motion.div
                    key={item.title}
                    className="rounded-xl border border-border bg-card p-3"
                    initial={{ opacity: 0, x: 12 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.2 + i * 0.12 }}
                  >
                    <p className="text-sm font-medium text-foreground">{item.title}</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{item.summary}</p>
                    <div className="mt-3 flex gap-2">
                      <span className="inline-flex items-center gap-1 rounded-md bg-brand px-2.5 py-1 text-[11px] font-semibold text-brand-foreground">
                        <Check className="h-3 w-3" />
                        Approve
                      </span>
                      <span className="rounded-md border border-border px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
                        Reject
                      </span>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
