import Image from "next/image"
import { cn } from "@/lib/utils"

/**
 * Marketing scene — the app's grain-textured illustrations (public/illustrations)
 * in the same frame the workspace uses for its hero art: a soft wash panel with
 * an optional floating status chip. Keeps marketing pages visually in step with
 * the product screenshots instead of abstract placeholder art.
 */
type SceneTone = "green" | "amber" | "neutral"

const DOT: Record<SceneTone, string> = {
  green: "bg-[#19c37d]",
  amber: "bg-[#e2a33a]",
  neutral: "bg-[#8a8b85]",
}

export function MarketingScene({
  name,
  alt = "",
  width = 320,
  height = 230,
  status,
  tone = "green",
  aspect,
  priority = false,
  className,
}: {
  /** File name in public/illustrations, without extension. */
  name: string
  alt?: string
  width?: number
  height?: number
  /** Short line shown in the floating chip, e.g. "3 approvals cleared". */
  status?: string
  tone?: SceneTone
  /** Optional fixed aspect ratio class, e.g. "aspect-[4/3]"; defaults to the art's own. */
  aspect?: string
  priority?: boolean
  className?: string
}) {
  return (
    <figure
      className={cn(
        "relative overflow-hidden rounded-2xl border border-divide bg-[#e7ece3]",
        aspect,
        className,
      )}
    >
      <Image
        src={`/illustrations/${name}.svg`}
        alt={alt}
        aria-hidden={alt ? undefined : true}
        width={width}
        height={height}
        priority={priority}
        unoptimized
        draggable={false}
        className={cn("block w-full", aspect ? "h-full object-cover" : "h-auto")}
      />
      {status ? (
        <figcaption className="absolute right-3 bottom-3 left-3 flex items-center gap-2 rounded-xl border border-[#e4e4df] bg-white/95 px-3 py-2 text-[13px] text-[#262826] shadow-[0_6px_16px_rgba(20,20,20,0.08)]">
          <i aria-hidden className={cn("size-2 flex-none rounded-full", DOT[tone])} />
          {status}
        </figcaption>
      ) : null}
    </figure>
  )
}
