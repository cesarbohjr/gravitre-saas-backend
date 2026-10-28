import React from "react"
import Image from "next/image"

/**
 * Auth side panel — Gravitre copy only (no invented testimonials). Uses the
 * workspace's own revenue illustration so sign-in looks like the app it opens.
 */
export function AuthIllustration() {
  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-divide bg-[#e7ece3]">
      <Image
        src="/illustrations/market-revenue.svg"
        alt=""
        aria-hidden
        width={300}
        height={190}
        priority
        unoptimized
        draggable={false}
        className="mk-scene-drift block h-auto w-full"
      />
      <div className="relative -mt-10 px-4 pb-4 md:px-8 md:pb-8">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          {["Agents", "Workflows", "Approvals"].map((chip) => (
            <p
              key={chip}
              className="rounded-md border border-[#e4e4df] bg-white/90 px-2 py-1 text-xs text-[#3f4b45]"
            >
              {chip}
            </p>
          ))}
        </div>
        <div className="max-w-sm rounded-xl border border-[#e4e4df] bg-white/95 p-4 shadow-[0_6px_16px_rgba(20,20,20,0.08)]">
          <h2 className="text-lg font-medium text-[#141513] md:text-xl">
            One AI brain for your entire business.
          </h2>
          <p className="mt-3 text-sm text-[#59665f]">
            Connect tools, coordinate agents and people, measure outcomes, and improve
            with human approval where it matters.
          </p>
        </div>
      </div>
    </div>
  )
}
