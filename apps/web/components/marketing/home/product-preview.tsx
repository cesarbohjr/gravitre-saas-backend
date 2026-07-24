"use client"

import { motion, useScroll, useTransform } from "framer-motion"
import { Sparkles } from "lucide-react"
import { useRef } from "react"
import { buildOperationalSuccessClaim, EMPTY_LIVE_INTEL } from "@/lib/marketing-intelligence-truth"

export function ProductPreview() {
  const ref = useRef(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  })
  const y = useTransform(scrollYProgress, [0, 1], [100, -100])
  const opacity = useTransform(scrollYProgress, [0, 0.3, 0.7, 1], [0, 1, 1, 0])

  return (
    <motion.div ref={ref} style={{ y, opacity }} className="relative">
      <div className="absolute -inset-4 rounded-3xl bg-gradient-to-b from-emerald-200/30 via-transparent to-transparent blur-2xl" />
      <div className="relative rounded-2xl border border-zinc-200 bg-white p-2 shadow-2xl">
        <div className="rounded-xl border border-zinc-100 bg-zinc-50 overflow-hidden">
          <div className="flex items-center gap-2 border-b border-zinc-200 bg-white px-4 py-3">
            <div className="flex gap-1.5">
              <div className="h-3 w-3 rounded-full bg-red-400" />
              <div className="h-3 w-3 rounded-full bg-yellow-400" />
              <div className="h-3 w-3 rounded-full bg-green-400" />
            </div>
            <div className="flex-1 text-center">
              <span className="text-xs text-zinc-400 font-mono">gravitre.app/ai</span>
            </div>
          </div>
          <div className="aspect-[16/9] bg-gradient-to-br from-zinc-50 to-white p-6 sm:p-8">
            <div className="grid h-full grid-cols-12 gap-4">
              <div className="col-span-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <motion.div
                      key={i}
                      className="flex items-center gap-2"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.1 }}
                    >
                      <div className={`h-2 w-2 rounded-full ${i === 2 ? "bg-emerald-500" : "bg-zinc-300"}`} />
                      <div className={`h-2 rounded ${i === 2 ? "w-16 bg-zinc-400" : "w-12 bg-zinc-200"}`} />
                    </motion.div>
                  ))}
                </div>
              </div>
              <div className="col-span-6 space-y-4">
                <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <motion.div
                      className="h-10 w-10 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-md"
                      animate={{ scale: [1, 1.05, 1] }}
                      transition={{ duration: 2, repeat: Infinity }}
                    >
                      <Sparkles strokeWidth={1.5} className="h-5 w-5 text-white" />
                    </motion.div>
                    <div className="flex-1">
                      <div className="h-2 w-32 rounded bg-zinc-300" />
                      <div className="mt-1 h-2 w-24 rounded bg-zinc-200" />
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
                  <motion.div
                    className="h-2 w-full rounded bg-emerald-300"
                    animate={{ width: ["0%", "100%"] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  />
                </div>
              </div>
              <div className="col-span-3 rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
                <div className="text-xs text-zinc-400 mb-3 font-medium">Metrics</div>
                <div className="space-y-3">
                  {(() => {
                    const success = buildOperationalSuccessClaim(EMPTY_LIVE_INTEL)
                    return (
                      <div>
                        <div className="text-xs text-zinc-500 mb-1 leading-snug">{success.eyebrow}</div>
                        <div className="text-sm font-medium text-emerald-700 leading-snug">{success.primary}</div>
                        <p className="mt-2 text-[10px] text-zinc-400 leading-relaxed">
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
