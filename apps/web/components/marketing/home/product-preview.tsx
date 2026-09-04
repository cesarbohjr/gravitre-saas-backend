"use client"

import { motion, useScroll, useTransform } from "framer-motion"
import { Sparkles } from "lucide-react"
import { useRef } from "react"
import { buildOperationalSuccessClaim, EMPTY_LIVE_INTEL } from "@/lib/marketing-intelligence-truth"
import { useMotionPrefs } from "@/lib/animations"

/** Dominant hero visual — product shell mock; honesty copy only (no fabricated %). */
export function ProductPreview() {
  const ref = useRef(null)
  const { reduced } = useMotionPrefs()
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  })
  const y = useTransform(scrollYProgress, [0, 1], [reduced ? 0 : 100, reduced ? 0 : -100])
  const opacity = useTransform(
    scrollYProgress,
    [0, 0.3, 0.7, 1],
    reduced ? [1, 1, 1, 1] : [0, 1, 1, 0],
  )

  return (
    <motion.div ref={ref} style={{ y, opacity }} className="relative">
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-b from-primary/20 via-transparent to-transparent blur-2xl" />
      <div className="relative rounded-2xl border border-border bg-card p-2 shadow-2xl">
        <div className="overflow-hidden rounded-xl border border-border/70 bg-muted/40">
          <div className="flex items-center gap-2 border-b border-border bg-card px-4 py-3">
            <div className="flex gap-1.5">
              <div className="h-3 w-3 rounded-full bg-red-400" />
              <div className="h-3 w-3 rounded-full bg-yellow-400" />
              <div className="h-3 w-3 rounded-full bg-green-400" />
            </div>
            <div className="flex-1 text-center">
              <span className="font-mono text-xs text-muted-foreground">gravitre.app/ai</span>
            </div>
          </div>
          <div className="aspect-[16/9] bg-gradient-to-br from-muted/50 to-card p-6 sm:p-8">
            <div className="grid h-full grid-cols-12 gap-4">
              <div className="col-span-3 rounded-lg border border-border bg-card p-4 shadow-sm">
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <motion.div
                      key={i}
                      className="flex items-center gap-2"
                      initial={reduced ? false : { opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: reduced ? 0 : i * 0.1 }}
                    >
                      <div
                        className={`h-2 w-2 rounded-full ${i === 2 ? "bg-primary" : "bg-muted-foreground/30"}`}
                      />
                      <div
                        className={`h-2 rounded ${i === 2 ? "w-16 bg-muted-foreground/50" : "w-12 bg-muted-foreground/25"}`}
                      />
                    </motion.div>
                  ))}
                </div>
              </div>
              <div className="col-span-6 space-y-4">
                <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <motion.div
                      className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-primary to-emerald-600 shadow-md"
                      animate={reduced ? undefined : { scale: [1, 1.05, 1] }}
                      transition={reduced ? undefined : { duration: 2, repeat: Infinity }}
                    >
                      <Sparkles strokeWidth={1.5} className="h-5 w-5 text-primary-foreground" />
                    </motion.div>
                    <div className="flex-1">
                      <div className="h-2 w-32 rounded bg-muted-foreground/40" />
                      <div className="mt-1 h-2 w-24 rounded bg-muted-foreground/25" />
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border border-primary/25 bg-primary/10 p-4">
                  <motion.div
                    className="h-2 w-full rounded bg-primary/50"
                    animate={reduced ? undefined : { width: ["0%", "100%"] }}
                    transition={reduced ? undefined : { duration: 3, repeat: Infinity }}
                  />
                </div>
              </div>
              <div className="col-span-3 rounded-lg border border-border bg-card p-4 shadow-sm">
                <div className="mb-3 text-xs font-medium text-muted-foreground">Metrics</div>
                <div className="space-y-3">
                  {(() => {
                    const success = buildOperationalSuccessClaim(EMPTY_LIVE_INTEL)
                    return (
                      <div>
                        <div className="mb-1 text-xs leading-snug text-muted-foreground">
                          {success.eyebrow}
                        </div>
                        <div className="text-sm font-medium leading-snug text-primary">
                          {success.primary}
                        </div>
                        <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
                          Live run telemetry in your workspace — never a fabricated public %
                        </p>
                      </div>
                    )
                  })()}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
