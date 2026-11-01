import Image from "next/image"
import { cn } from "@/lib/utils"

/**
 * Marketing scene — the app's grain-textured illustrations (public/illustrations)
 * in the same frame the workspace uses for its hero art: a soft wash panel with
 * an optional floating status chip. The animated marketing/* set drops the panel
 * and sits on the Nodus dot field instead. Keeps marketing pages visually in step with
 * the product screenshots instead of abstract placeholder art. The art drifts
 * slowly (mk-scene-drift in globals.css) and holds still under reduced motion.
 */
type SceneTone = "green" | "amber" | "neutral"

const DOT: Record<SceneTone, string> = {
  green: "bg-[#19c37d]",
  amber: "bg-[#e2a33a]",
  neutral: "bg-[#8a8b85]",
}

/** Stable per-image offset so scenes on one page don't drift in lockstep. */
function hash(value: string) {
  let h = 0
  for (let i = 0; i < value.length; i++) h = (h * 31 + value.charCodeAt(i)) >>> 0
  return h
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
  /** Path under public/illustrations, without extension, e.g. "marketing/support". */
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
  const animated = name.startsWith("marketing/")
  return (
    <figure
      className={cn(
        "relative overflow-hidden",
        // Marketing art has no backdrop of its own: it sits on the Nodus dot
        // field (same as the How it works / Benefits graphics) so it blends in.
        animated ? "isolate" : "rounded-2xl border border-divide bg-[#e7ece3]",
        aspect,
        className,
      )}
    >
      {animated ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(var(--color-dots)_1px,transparent_1px)] mask-radial-from-10% [background-size:10px_10px]"
        />
      ) : null}
      <Image
        src={`/illustrations/${name}.svg`}
        alt={alt}
        aria-hidden={alt ? undefined : true}
        width={width}
        height={height}
        priority={priority}
        unoptimized
        draggable={false}
        style={animated ? undefined : { animationDelay: `${-(hash(name) % 14)}s` }}
        className={cn(
          animated ? "mask-x-from-92% mask-y-from-92%" : "mk-scene-drift",
          "block w-full",
          aspect ? "h-full object-cover" : "h-auto",
        )}
      />
      {status ? (
        <figcaption className="absolute right-3 bottom-3 left-3 flex items-center gap-2 rounded-xl border border-[#e4e4df] bg-white/95 px-3 py-2 text-[13px] text-[#262826] shadow-[0_6px_16px_rgba(20,20,20,0.08)]">
          <i aria-hidden className={cn("mk-scene-pulse size-2 flex-none rounded-full", DOT[tone])} />
          {status}
        </figcaption>
      ) : null}
    </figure>
  )
}
