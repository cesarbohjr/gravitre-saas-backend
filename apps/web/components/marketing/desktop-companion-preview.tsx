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
      <div className="pointer-events-none absolute -inset-6 rounded-[2rem] bg-gradient-to-b from-emerald-200/25 via-transparent to-transparent blur-2xl" />

      {/* Floating accent chips */}
      <motion.div
        className="absolute -left-2 top-10 z-10 hidden rounded-2xl border border-zinc-200/80 bg-white/90 px-3 py-2 shadow-lg shadow-zinc-900/10 backdrop-blur sm:flex sm:items-center sm:gap-2 lg:-left-8"
        animate={{ y: [0, -8, 0] }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
      >
        <Keyboard className="h-4 w-4 text-emerald-600" />
        <span className="text-xs font-semibold text-zinc-700">Alt+Space</span>
      </motion.div>
      <motion.div
        className="absolute -right-2 top-24 z-10 hidden rounded-2xl border border-zinc-200/80 bg-white/90 px-3 py-2 shadow-lg shadow-zinc-900/10 backdrop-blur sm:flex sm:items-center sm:gap-2 lg:-right-6"
        animate={{ y: [0, 10, 0] }}
        transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 0.8 }}
      >
        <Shield className="h-4 w-4 text-emerald-600" />
        <span className="text-xs font-semibold text-zinc-700">Approve writes</span>
      </motion.div>

      <div className="relative overflow-hidden rounded-[1.35rem] border border-zinc-200 bg-white p-2 shadow-[0_28px_80px_-36px_rgba(24,24,27,0.45)]">
        {/* macOS-style title bar */}
        <div className="flex items-center gap-2 rounded-t-[1.05rem] border-b border-zinc-100 bg-zinc-50 px-4 py-3">
          <div className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full bg-red-400" />
            <span className="h-3 w-3 rounded-full bg-amber-400" />
            <span className="h-3 w-3 rounded-full bg-emerald-400" />
          </div>
          <div className="flex-1 text-center">
            <span className="text-xs font-medium text-zinc-400">Gravitre Desktop</span>
          </div>
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
            Connected
          </span>
        </div>

        {/* Dark companion shell (matches apps/desktop) */}
        <div className="overflow-hidden rounded-b-[1.05rem] bg-[#0f1412] text-[#e8eee9]">
          <div className="flex items-center gap-2 border-b border-[#2a332e] bg-[#171c19] px-4 py-2.5">
            <span className="text-sm font-semibold tracking-tight">Gravitre</span>
            <span className="ml-auto rounded-full border border-[#16a374]/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-[#16a374]">
              Online
            </span>
          </div>

          <div className="flex gap-1 border-b border-[#2a332e] px-3 py-2">
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
                    ? "bg-[#16a374]/20 text-[#e8eee9]"
                    : "text-[#8b968f]",
                ].join(" ")}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </div>
            ))}
          </div>

          <div className="grid gap-0 sm:grid-cols-[1.15fr_0.85fr]">
            <div className="flex min-h-[280px] flex-col p-4 sm:min-h-[320px]">
              <div className="mb-3 inline-flex w-fit gap-1 rounded-full border border-[#2a332e] bg-[#171c19] p-0.5">
                <span className="rounded-full bg-[#16a374] px-2.5 py-0.5 text-[10px] font-semibold text-white">
                  Text
                </span>
                <span className="rounded-full px-2.5 py-0.5 text-[10px] font-medium text-[#8b968f]">
                  Voice
                </span>
              </div>

              <div className="flex-1 space-y-3">
                <motion.div
                  className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-[#16a374] px-3.5 py-2.5 text-sm leading-relaxed text-white"
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.15 }}
                >
                  Summarize pending approvals and draft a reply.
                </motion.div>
                <motion.div
                  className="max-w-[90%] rounded-2xl rounded-bl-md border border-[#2a332e] bg-[#171c19] px-3.5 py-2.5 text-sm leading-relaxed text-[#e8eee9]"
                  initial={{ opacity: 0, y: 8 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: 0.35 }}
                >
                  Two writes waiting. Approve from here — Outcomes stays in sync on the web.
                </motion.div>
                <p className="pt-1 text-[11px] text-[#8b968f]">
                  Summon anytime with Alt+Space · Option+Space on Mac
                </p>
              </div>

              <div className="mt-4 flex items-end gap-2 rounded-xl border border-[#2a332e] bg-[#171c19] p-2">
                <div className="min-h-[40px] flex-1 rounded-lg px-2 py-2 text-sm text-[#8b968f]">
                  Message Gravitre…
                </div>
                <div className="rounded-lg bg-[#16a374] px-3 py-2 text-xs font-semibold text-white">
                  Send
                </div>
              </div>
            </div>

            <div className="border-t border-[#2a332e] bg-[#121816] p-4 sm:border-l sm:border-t-0">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-[#8b968f]">
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
                    className="rounded-xl border border-[#2a332e] bg-[#171c19] p-3"
                    initial={{ opacity: 0, x: 12 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.2 + i * 0.12 }}
                  >
                    <p className="text-sm font-medium text-[#e8eee9]">{item.title}</p>
                    <p className="mt-1 text-xs leading-relaxed text-[#8b968f]">{item.summary}</p>
                    <div className="mt-3 flex gap-2">
                      <span className="inline-flex items-center gap-1 rounded-md bg-[#16a374] px-2.5 py-1 text-[11px] font-semibold text-white">
                        <Check className="h-3 w-3" />
                        Approve
                      </span>
                      <span className="rounded-md border border-[#2a332e] px-2.5 py-1 text-[11px] font-medium text-[#8b968f]">
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
