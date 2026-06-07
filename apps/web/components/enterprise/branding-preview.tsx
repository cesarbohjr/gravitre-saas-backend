"use client"

import Image from "next/image"
import { cn } from "@/lib/utils"

interface BrandingPreviewProps {
  logoUrl: string
  primaryColor: string
  hidePoweredBy: boolean
  emailFromName: string
  className?: string
}

export function BrandingPreview({
  logoUrl,
  primaryColor,
  hidePoweredBy,
  emailFromName,
  className,
}: BrandingPreviewProps) {
  const logo = logoUrl || "/images/gravitre-logo-white.png"

  return (
    <div
      className={cn("overflow-hidden rounded-xl border border-border bg-[#0B0F14] shadow-lg", className)}
      style={{ ["--preview-primary" as string]: primaryColor }}
    >
      <div className="border-b border-white/10 px-3 py-2">
        <p className="text-[10px] uppercase tracking-wider text-white/50">Live preview</p>
      </div>
      <div className="flex min-h-[220px]">
        <aside className="w-14 shrink-0 border-r border-white/10 bg-[#11161D] p-2">
          <div className="relative mx-auto h-8 w-8 overflow-hidden rounded-md bg-white/5">
            <Image src={logo} alt="" fill className="object-contain p-1" unoptimized />
          </div>
          <div className="mt-3 space-y-1.5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="mx-auto h-1.5 w-6 rounded-full bg-white/10" />
            ))}
          </div>
        </aside>
        <div className="flex flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-white/10 px-3 py-2">
            <span className="text-xs font-medium text-white/90">{emailFromName || "Gravitre"}</span>
            <div
              className="h-6 rounded-md px-2 text-[10px] font-medium leading-6 text-white"
              style={{ backgroundColor: primaryColor }}
            >
              Action
            </div>
          </header>
          <div className="flex-1 space-y-2 p-3">
            <div className="h-2 w-2/3 rounded bg-white/10" />
            <div className="h-2 w-1/2 rounded bg-white/10" />
            <div
              className="mt-4 h-8 w-full rounded-md border border-white/10"
              style={{ boxShadow: `inset 0 0 0 1px ${primaryColor}40` }}
            />
          </div>
          {!hidePoweredBy && (
            <footer className="border-t border-white/10 px-3 py-2 text-[10px] text-white/40">
              Powered by Gravitre
            </footer>
          )}
        </div>
      </div>
    </div>
  )
}
