"use client"

import { motion, useScroll, useTransform } from "framer-motion"
import Image from "next/image"
import { Keyboard, Shield } from "lucide-react"
import { useRef } from "react"
import { NodusDotField } from "@/components/marketing/nodus/dot-field"

/**
 * Desktop companion window for the download page: a real capture of the
 * redesigned apps/desktop Home inside a light window frame.
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
      <NodusDotField className="-inset-x-24 -inset-y-12" />

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
            "linear-gradient(to bottom, black 0%, black 90%, transparent 100%)",
          WebkitMaskImage:
            "linear-gradient(to bottom, black 0%, black 90%, transparent 100%)",
        }}
      >
        {/* Title bar — macOS window outline, matching the other product shots */}
        <div className="flex items-center gap-2 rounded-t-[1.05rem] border-b border-border bg-card px-4 py-3">
          <div className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full bg-[rgba(239,68,68,0.5)]" />
            <span className="h-3 w-3 rounded-full bg-[rgba(234,179,8,0.5)]" />
            <span className="h-3 w-3 rounded-full bg-[rgba(34,181,90,0.55)]" />
          </div>
          <div className="flex-1 text-center">
            <span className="text-xs font-medium text-muted-foreground">Gravitre Desktop</span>
          </div>
          <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-primary">
            Connected
          </span>
        </div>

        {/* Real capture of apps/desktop Home (fixture data, no customer tenant). */}
        <Image
          src="/product/desktop-home.png"
          alt="Gravitre Desktop home: approvals waiting, assignments in progress, and Ask"
          width={2360}
          height={1280}
          sizes="(max-width: 896px) 100vw, 896px"
          className="block w-full rounded-b-[1.05rem]"
          draggable={false}
        />
      </div>
    </motion.div>
  )
}
