import Image from "next/image"
import { cn } from "@/lib/utils"

/**
 * Real UI captures from scripts/capture-product-shots.mjs (2880x1800 @2x).
 *
 * `caption` is REQUIRED on purpose. Every shot is rendered against seeded
 * fixture data in apps/web/lib/e2e-shot-fixtures.ts, so the workspace name,
 * counts, and latency figures are illustrative rather than customer data.
 * Module C honesty rules mean a screenshot must never be wired in bare and
 * left to imply those numbers are real production metrics — making the prop
 * mandatory is what stops that happening by omission.
 */
export interface ProductScreenshotProps {
  /** Path under /public, e.g. "/product/app-approvals.png". */
  src: string
  /** Describe the UI state shown, not just the page name. */
  alt: string
  /** Visible provenance note. Keep it short and factual. */
  caption: string
  /** Set on the first shot above the fold only. */
  priority?: boolean
  className?: string
}

export function ProductScreenshot({
  src,
  alt,
  caption,
  priority = false,
  className,
}: ProductScreenshotProps) {
  return (
    <figure className={cn("flex flex-col gap-3", className)}>
      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
        <Image
          src={src}
          alt={alt}
          width={2880}
          height={1800}
          priority={priority}
          sizes="(min-width: 1024px) 960px, 100vw"
          className="h-auto w-full"
        />
      </div>
      <figcaption className="text-[10px] uppercase tracking-wide text-amber-600">
        {caption}
      </figcaption>
    </figure>
  )
}
