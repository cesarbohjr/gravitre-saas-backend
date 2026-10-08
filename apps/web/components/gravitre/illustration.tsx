/**
 * Gravitre illustration library (editorial, paper-grain scenes) served from
 * /public/illustrations. Placement follows the library guidance:
 *  - header-*  wide 3:1 scenes to the right of a page title
 *  - spot-*    objects only, top of a feature card
 *  - moment-*  small scene above one line of copy in an empty or error state
 *  - dept-*    department scene beside a short paragraph between data blocks
 *  - market-*  objects-only marketplace category art (template cards and template hero)
 * Illustrations are decorative: they never carry information the copy lacks.
 */
import { cn } from "@/lib/utils"

export const ILLUSTRATIONS = {
  "header-team-at-work": { w: 640, h: 220 },
  "header-quiet-desk": { w: 640, h: 220 },
  "dept-sales": { w: 420, h: 260 },
  "dept-marketing": { w: 420, h: 260 },
  "dept-operations": { w: 420, h: 260 },
  "dept-finance": { w: 420, h: 260 },
  "dept-support": { w: 420, h: 260 },
  "dept-engineering": { w: 420, h: 260 },
  "spot-agents": { w: 300, h: 190 },
  "spot-workflows": { w: 300, h: 190 },
  "spot-connectors": { w: 300, h: 190 },
  "spot-knowledge": { w: 300, h: 190 },
  "spot-schedules": { w: 300, h: 190 },
  "spot-governance": { w: 300, h: 190 },
  "spot-approvals": { w: 300, h: 190 },
  "spot-reports": { w: 300, h: 190 },
  "moment-all-clear": { w: 320, h: 230 },
  "moment-needs-decision": { w: 320, h: 230 },
  "moment-error": { w: 320, h: 230 },
  "moment-welcome": { w: 320, h: 230 },
  "moment-team-meeting": { w: 320, h: 230 },
  "moment-milestone": { w: 320, h: 230 },
  "moment-focus-time": { w: 320, h: 230 },
  "moment-remote-call": { w: 320, h: 230 },
  "header-goals-office": { w: 640, h: 220 },
  "header-empty-desk": { w: 640, h: 220 },
  "goal-template-marketing": { w: 420, h: 260 },
  "goal-template-finance": { w: 420, h: 260 },
  "goal-template-support": { w: 420, h: 260 },
  "feature-assignment-workflow": { w: 420, h: 260 },
  "spot-report-easel": { w: 300, h: 190 },
  "moment-paused-agents": { w: 300, h: 190 },
  "moment-unplugged": { w: 320, h: 230 },
  "moment-inbox-zero": { w: 320, h: 190 },
  "moment-request-waiting": { w: 320, h: 230 },
  "moment-no-addons": { w: 320, h: 190 },
  "moment-high-five": { w: 320, h: 230 },
  "market-prospecting": { w: 300, h: 190 },
  "market-compliance": { w: 300, h: 190 },
  "market-security": { w: 300, h: 190 },
  "market-finance": { w: 300, h: 190 },
  "market-product": { w: 300, h: 190 },
  "market-support": { w: 300, h: 190 },
  "market-onboarding": { w: 300, h: 190 },
  "market-pipeline": { w: 300, h: 190 },
  "market-deals": { w: 300, h: 190 },
  "market-campaigns": { w: 300, h: 190 },
  "market-site-health": { w: 300, h: 190 },
  "market-revenue": { w: 300, h: 190 },
  "market-tickets": { w: 300, h: 190 },
  "market-new-customers": { w: 300, h: 190 },
  "market-leads": { w: 300, h: 190 },
} as const

export type IllustrationName = keyof typeof ILLUSTRATIONS

export function Illustration({
  name,
  width,
  className,
  priority = false,
}: {
  name: IllustrationName
  /** Rendered width in px; height follows the scene's aspect ratio. */
  width: number
  className?: string
  priority?: boolean
}) {
  const box = ILLUSTRATIONS[name]
  const height = Math.round((width * box.h) / box.w)
  return (
    // eslint-disable-next-line @next/next/no-img-element -- static SVG scene, no optimisation needed
    <img
      src={`/illustrations/${name}.svg`}
      alt=""
      aria-hidden
      width={width}
      height={height}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      data-illustration={name}
      className={cn(
        "pointer-events-none block h-auto max-w-full select-none rounded-xl dark:opacity-90",
        className,
      )}
      style={{ width }}
    />
  )
}
