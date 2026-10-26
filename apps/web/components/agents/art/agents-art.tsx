"use client"

import { useId, type ReactNode } from "react"
import "./agents-art.css"

/**
 * Animated hero scenes from the Agents designs (Activity, Approvals, Sources and
 * the access card). Each scene is drawn from live state, so the picture never
 * claims something the page does not: the Sources hub shows as many broken pipes
 * as there are failing sources, the run timeline only shows a failed step when an
 * outcome actually failed, and the decision monitor shows a waiting card only when
 * something is waiting.
 *
 * Every scene shares one frame: a blurred colour wash, a dot field fading in from
 * the right, a ground line and film grain. Motion stops under reduced motion.
 */

export type Wash = { cx: number; cy: number; rx: number; ry: number; fill: string }

export function ArtFrame({
  label,
  wash,
  ground = [20, 300],
  children,
}: {
  label: string
  wash: Wash
  /** Ground line ends; the Dashboard scenes draw a slightly shorter one. */
  ground?: [number, number]
  children: ReactNode
}) {
  const raw = useId()
  const id = `ag${raw.replace(/[^a-zA-Z0-9]/g, "")}`
  return (
    <div className="ag-art">
      <svg role="img" aria-label={label} viewBox="0 0 320 260" preserveAspectRatio="xMidYMid slice">
        <defs>
          <filter id={`${id}b`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="19.2" />
          </filter>
          <pattern id={`${id}d`} width="9" height="9" patternUnits="userSpaceOnUse">
            <circle cx="1.8" cy="1.8" r="1.0" fill="#2A2B28" />
          </pattern>
          <linearGradient id={`${id}f`} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0.3" stopColor="#FFFFFF" stopOpacity="0" />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity="1" />
          </linearGradient>
          <mask id={`${id}m`}>
            <rect width="320" height="260" fill={`url(#${id}f)`} />
          </mask>
          <filter id={`${id}g`} x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves={2} stitchTiles="stitch" />
            <feColorMatrix values="0 0 0 0 0.15 0 0 0 0 0.13 0 0 0 0 0.1 0.9 0 0 0 -0.38" />
          </filter>
        </defs>
        <rect width="320" height="260" fill="#E7ECE3" />
        <g filter={`url(#${id}b)`}>
          <circle className="g-mesh" cx="38" cy="21" r="96" fill="#CFDCCB" opacity="0.9" />
          <ellipse cx={wash.cx} cy={wash.cy} rx={wash.rx} ry={wash.ry} fill={wash.fill} />
          <circle className="g-mesh" cx="301" cy="10" r="83" fill="#DCE3E8" style={{ animationDelay: "-7s" }} />
          <circle className="g-mesh" cx="275" cy="265" r="77" fill="#EBDCC0" opacity="0.8" style={{ animationDelay: "-12s" }} />
        </g>
        <rect width="320" height="260" fill={`url(#${id}d)`} opacity="0.2" mask={`url(#${id}m)`} />
        {children}
        <line x1={ground[0]} y1="214" x2={ground[1]} y2="214" stroke="#9C8C74" strokeWidth="2" />
        <rect width="320" height="260" filter={`url(#${id}g)`} opacity="0.55" />
      </svg>
    </div>
  )
}

/** A standing figure; `children` draws the arms and anything they hold. */
function Person({
  x,
  shirt,
  skin = "#D6AB86",
  hair = "#2E231D",
  bun,
  short,
  children,
}: {
  x: number
  shirt: string
  skin?: string
  hair?: string
  /** Hair bun offset (left negative), or none. */
  bun?: number
  /** Short cropped hair instead of the swept fringe. */
  short?: boolean
  children?: ReactNode
}) {
  return (
    <g transform={`translate(${x} 0)`}>
      <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" />
      <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" />
      <path d="M-13 124 Q0 116 13 124 L15 168 L-15 168 Z" fill={shirt} />
      {children}
      <circle cx="0" cy="106" r="10" fill={skin} />
      {short ? (
        <path d="M-10.5 106 A10.5 10.5 0 0 1 10.5 106 L10 102 Q0 96 -10.5 106 Z" fill={hair} />
      ) : (
        <path d="M-10.5 105 A10.5 10.5 0 0 1 10.5 105 Q2 97 -10.5 105 Z" fill={hair} />
      )}
      {bun != null ? <circle cx={bun} cy="97" r="4.5" fill={hair} /> : null}
    </g>
  )
}

const STEP_X = [62, 114, 166, 218, 270]

/** Activity: a five-step run timeline. With a failure, step four is red and under the magnifying glass. */
export function ActivityArt({ failed }: { failed: boolean }) {
  const failAt = failed ? 3 : -1
  return (
    <ArtFrame
      label={failed ? "Run timeline with one failed step under a magnifying glass" : "Run timeline with every step passing"}
      wash={{ cx: 160, cy: 124, rx: 149, ry: 110, fill: "#E6DFD0" }}
    >
      {STEP_X.map((cx, i) => (
        <g key={cx}>
          <rect
            x={cx - 22}
            y="30"
            width="44"
            height="30"
            rx="5"
            fill="#F5F2EA"
            stroke={i === failAt ? "#A3333D" : "#D6CFBF"}
            strokeWidth={i === failAt ? 1.6 : 1}
          />
          <rect x={cx - 15} y="38" width="28" height="4" rx="2" fill={i === failAt ? "#E3C3C6" : "#C9C4B8"} />
          <rect x={cx - 15} y="47" width="20" height="4" rx="2" fill={i === failAt ? "#E3C3C6" : "#C9C4B8"} />
          <line x1={cx} y1="60" x2={cx} y2="78" stroke={i === failAt ? "#E3C3C6" : "#C9C4B8"} strokeWidth="1.5" />
        </g>
      ))}
      <line x1="40" y1="78" x2="292" y2="78" stroke="#8A8985" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="40" cy="78" r="4" fill="#4CC27F" className="g-run" />
      {STEP_X.map((cx, i) =>
        i === failAt ? (
          <g key={cx}>
            <circle cx={cx} cy="78" r="11" fill="none" stroke="#A3333D" strokeWidth="1.5" className="g-ring" />
            <circle cx={cx} cy="78" r="7" fill="#A3333D" />
            <path d={`M${cx - 2.5} 75.5 l5 5 M${cx + 2.5} 75.5 l-5 5`} stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round" />
          </g>
        ) : i === 4 && failed ? (
          <circle key={cx} cx={cx} cy="78" r="7" fill="#F5F2EA" stroke="#8A8985" strokeWidth="2" />
        ) : (
          <g key={cx}>
            <circle cx={cx} cy="78" r="7" fill="#2E9E5B" />
            <path d={`M${cx - 3} 78 l2 2 l4 -4`} fill="none" stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        ),
      )}
      {failed ? (
        <g className="g-bob">
          <circle cx="214" cy="96" r="15" fill="#FFFFFF" fillOpacity="0.35" stroke="#26282C" strokeWidth="3.5" />
          <line x1="225" y1="107" x2="236" y2="120" stroke="#26282C" strokeWidth="5" strokeLinecap="round" />
        </g>
      ) : null}
      <Person x={256} shirt="#4A6A8E" skin="#C99572" hair="#1F1A17" short>
        <path d="M-10 128 L-16 124 L-20 122" fill="none" stroke="#4A6A8E" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-20" cy="121" r="3.4" fill="#C99572" />
        <path d="M10 128 L13 160" stroke="#4A6A8E" strokeWidth="6" strokeLinecap="round" />
        <circle cx="13" cy="162" r="3.2" fill="#C99572" />
      </Person>
      <Person x={96} shirt="#C9A24B" bun={-8}>
        <rect x="12" y="128" width="20" height="26" rx="3" fill="#3B4250" />
        <rect x="15" y="132" width="14" height="3" rx="1.5" fill="#4CC27F" className="g-pulse" />
        <path d="M-10 128 L-12 160" stroke="#C9A24B" strokeWidth="6" strokeLinecap="round" />
        <circle cx="-12" cy="162" r="3.2" fill="#D6AB86" />
        <path d="M9 128 L16 142 L20 140" fill="none" stroke="#C9A24B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="21" cy="139" r="3.2" fill="#D6AB86" />
      </Person>
    </ArtFrame>
  )
}

/** Approvals: request cards beside a monitor with approve and reject. The front card turns amber while anything waits. */
export function ApprovalsArt({ waiting }: { waiting: number }) {
  const clear = waiting <= 0
  return (
    <ArtFrame
      label={
        clear
          ? "Decision queue is clear; request cards beside a monitor with approve and reject"
          : `${waiting} request${waiting === 1 ? "" : "s"} waiting beside a monitor with approve and reject`
      }
      wash={{ cx: 166, cy: 126, rx: 147, ry: 110, fill: clear ? "#DCE5DC" : "#EDE3CF" }}
    >
      <path d="M112 84 C136 84 140 92 160 92" fill="none" stroke="#8A8985" strokeWidth="1.6" strokeDasharray="3 5" className="g-flow" />
      <g transform="rotate(-6 70 150)">
        <rect x="34" y="138" width="78" height="30" rx="6" fill="#F5F2EA" />
        <rect x="34" y="138" width="5" height="30" rx="2" fill="#B8875A" />
        <rect x="46" y="146" width="40" height="4" rx="2" fill="#C9C4B8" />
        <rect x="46" y="155" width="54" height="4" rx="2" fill="#E2DED4" />
      </g>
      <g transform="rotate(-3 70 114)">
        <rect x="34" y="102" width="78" height="30" rx="6" fill="#F5F2EA" />
        <rect x="34" y="102" width="5" height="30" rx="2" fill="#3D6FD1" />
        <rect x="46" y="110" width="40" height="4" rx="2" fill="#C9C4B8" />
        <rect x="46" y="119" width="54" height="4" rx="2" fill="#E2DED4" />
      </g>
      <g className="g-float">
        <rect x="34" y="66" width="78" height="30" rx="6" fill="#FFFFFF" stroke={clear ? "#2E9E5B" : "#E2A33A"} strokeWidth="1.5" />
        <rect x="34" y="66" width="5" height="30" rx="2" fill="#5B5BD6" />
        <rect x="46" y="74" width="40" height="4" rx="2" fill="#2B2D31" />
        <rect x="46" y="83" width="54" height="4" rx="2" fill="#C9C4B8" />
        {clear ? null : (
          <g className="g-beat">
            <circle cx="110" cy="68" r="9" fill="#E2A33A" />
            <text x="110" y="71.5" textAnchor="middle" fontSize="10" fontWeight="700" fill="#FFFFFF" fontFamily="Geist, system-ui, sans-serif">
              {waiting > 9 ? "9+" : waiting}
            </text>
          </g>
        )}
      </g>
      <rect x="160" y="40" width="118" height="92" rx="10" fill="#22272D" />
      <rect x="166" y="46" width="106" height="80" rx="6" fill="#F5F2EA" />
      <rect x="174" y="54" width="48" height="6" rx="3" fill="#2B2D31" />
      <rect x="174" y="66" width="86" height="4" rx="2" fill="#C9C4B8" />
      <rect x="174" y="75" width="70" height="4" rx="2" fill="#C9C4B8" />
      <rect x="171" y="97" width="48" height="24" rx="8" fill="none" stroke="#2E9E5B" strokeWidth="1.5" className="g-ring" />
      <rect x="174" y="100" width="42" height="18" rx="6" fill="#2E9E5B" />
      <path d="M188 109 l4 4 l8 -8" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="222" y="100" width="40" height="18" rx="6" fill="none" stroke="#A3333D" strokeWidth="1.8" />
      <path d="M238 105 l8 8 M246 105 l-8 8" stroke="#A3333D" strokeWidth="2" strokeLinecap="round" />
      <rect x="213" y="132" width="12" height="28" fill="#4A4F58" />
      <rect x="150" y="160" width="140" height="8" rx="2" fill="#6E5A44" />
      <rect x="158" y="168" width="5" height="46" fill="#6E5A44" />
      <rect x="277" y="168" width="5" height="46" fill="#6E5A44" />
      <rect x="244" y="150" width="28" height="10" rx="2" fill="#3B4250" />
      <g transform="translate(140 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <path d="M-14 124 Q0 116 14 124 L16 170 L-16 170 Z" fill="#2F3A48" />
        <path d="M-4 120 L0 132 L4 120 Z" fill="#F5F2EA" />
        <path d="M-1 124 L0 140 L1 124 Z" fill="#2E9E5B" />
        <path d="M-10 128 L-13 160" stroke="#2F3A48" strokeWidth="6" strokeLinecap="round" />
        <circle cx="-13" cy="162" r="3.2" fill="#C99572" />
        <g className="g-reach">
          <path d="M10 127 L24 118 L40 112" fill="none" stroke="#2F3A48" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="42" cy="111" r="3.4" fill="#C99572" />
        </g>
        <circle cx="0" cy="106" r="10" fill="#C99572" />
        <path d="M-10.5 106 A10.5 10.5 0 0 1 10.5 106 L10 102 Q0 96 -10.5 106 Z" fill="#1F1A17" />
      </g>
      <path d="M300 34 l2.5 6 l6 2.5 l-6 2.5 l-2.5 6 l-2.5 -6 l-6 -2.5 l6 -2.5 Z" fill="#C9A24B" className="g-twinkle" />
    </ArtFrame>
  )
}

const PIPES = [
  { d: "M92 72 C130 72 140 112 170 112", mark: { cx: 131, cy: 92 } },
  { d: "M92 132 L170 132", mark: { cx: 131, cy: 132 } },
  { d: "M92 190 C130 190 140 152 170 152", mark: { cx: 131, cy: 171 } },
]

const DATABASES = [
  { y: 58, body: "#4A6A8E", top: "#7C98B8", seam: "#3A5677" },
  { y: 118, body: "#5B5BD6", top: "#9C9CE8", seam: "#4646B8" },
  { y: 176, body: "#B8875A", top: "#D9B48C", seam: "#9A6E46" },
]

/** Sources: three databases piped into the Gravitre hub; up to three pipes break, one per failing source. */
export function SourcesArt({ broken }: { broken: number }) {
  const breaks = Math.max(0, Math.min(PIPES.length, broken))
  return (
    <ArtFrame
      label={
        breaks === 0
          ? "Databases piped into a Gravitre hub, every connection flowing"
          : `Databases piped into a Gravitre hub with ${broken} broken connection${broken === 1 ? "" : "s"}`
      }
      wash={{ cx: 164, cy: 126, rx: 149, ry: 110, fill: "#D9E1E6" }}
    >
      {PIPES.map((pipe, i) =>
        i >= PIPES.length - breaks ? (
          <g key={pipe.d}>
            <path d={pipe.d} fill="none" stroke="#C99A9F" strokeWidth="5" strokeLinecap="round" strokeDasharray="7 7" />
            <g className="g-pulse">
              <circle cx={pipe.mark.cx} cy={pipe.mark.cy} r="9" fill="#A3333D" />
              <path
                d={`M${pipe.mark.cx - 4} ${pipe.mark.cy - 4} l8 8 M${pipe.mark.cx + 4} ${pipe.mark.cy - 4} l-8 8`}
                stroke="#FFFFFF"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </g>
          </g>
        ) : (
          <g key={pipe.d}>
            <path d={pipe.d} fill="none" stroke="#8A8985" strokeWidth="5" strokeLinecap="round" />
            <path d={pipe.d} fill="none" stroke="#4CC27F" strokeWidth="2.2" strokeLinecap="round" strokeDasharray="3 9" className="g-flow" />
          </g>
        ),
      )}
      {DATABASES.map((db) => (
        <g key={db.y}>
          <rect x="44" y={db.y} width="48" height="30" fill={db.body} />
          <ellipse cx="68" cy={db.y + 30} rx="24" ry="7" fill={db.body} />
          <ellipse cx="68" cy={db.y} rx="24" ry="7" fill={db.top} />
          <path d={`M44 ${db.y + 12} Q68 ${db.y + 20} 92 ${db.y + 12}`} fill="none" stroke={db.seam} strokeWidth="1.5" />
        </g>
      ))}
      <rect x="168" y="100" width="64" height="64" rx="16" fill="#22272D" />
      <rect x="182" y="116" width="36" height="7" rx="3.5" fill="#4CC27F" className="g-pulse" />
      <rect x="182" y="129" width="28" height="7" rx="3.5" fill="#2E9E5B" className="g-pulse" style={{ animationDelay: "0.4s" }} />
      <rect x="182" y="142" width="20" height="7" rx="3.5" fill="#1F7A4A" className="g-pulse" style={{ animationDelay: "0.8s" }} />
      <path d="M232 140 C246 140 248 156 258 156" fill="none" stroke="#26282C" strokeWidth="3" strokeLinecap="round" />
      <rect x="254" y="150" width="12" height="12" rx="2" fill="#3B4048" />
      <Person x={276} shirt="#7C8F6B" bun={8}>
        <path d="M-10 128 L-18 146 L-12 156" fill="none" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-11" cy="157" r="3.2" fill="#D6AB86" />
        <path d="M10 128 L13 160" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" />
        <circle cx="13" cy="162" r="3.2" fill="#D6AB86" />
      </Person>
      <path d="M204 40 l2.5 6 l6 2.5 l-6 2.5 l-2.5 6 l-2.5 -6 l-6 -2.5 l6 -2.5 Z" fill="#2E9E5B" opacity="0.85" className="g-twinkle" />
    </ArtFrame>
  )
}

/** Access: a person carrying a large key toward a locked shield. Used where a page is locked to admins. */
export function AccessArt() {
  return (
    <ArtFrame label="A person carrying a large key toward a locked shield" wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#E6CED0" }}>
      <path
        className="g-ring"
        d="M212 50 L258 66 V114 C258 150 238 172 212 188 C186 172 166 150 166 114 V66 Z"
        fill="none"
        stroke="#A3333D"
        strokeWidth="2"
      />
      <path d="M212 50 L258 66 V114 C258 150 238 172 212 188 C186 172 166 150 166 114 V66 Z" fill="#A3333D" />
      <path
        d="M212 62 L248 75 V114 C248 143 232 161 212 175 C192 161 176 143 176 114 V75 Z"
        fill="none"
        stroke="#E9C7CA"
        strokeWidth="2"
        opacity="0.7"
      />
      <circle cx="212" cy="106" r="11" fill="#F3E8E2" />
      <path d="M206 112 L218 112 L222 140 L202 140 Z" fill="#F3E8E2" />
      <rect x="44" y="184" width="30" height="30" rx="4" fill="#C9A24B" />
      <path d="M50 184 V174 A9 9 0 0 1 68 174 V184" fill="none" stroke="#6B5A3A" strokeWidth="4" />
      <circle cx="59" cy="197" r="3" fill="#6B5A3A" />
      <rect x="58" y="198" width="2" height="7" fill="#6B5A3A" />
      <Person x={112} shirt="#3F5A7A" bun={-8}>
        <path d="M-9 129 L8 142 L26 142" fill="none" stroke="#344C68" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
      </Person>
      <g className="g-nudge">
        <circle cx="146" cy="136" r="9" fill="none" stroke="#C9A24B" strokeWidth="5" />
        <rect x="154" y="133" width="36" height="6" rx="2" fill="#C9A24B" />
        <rect x="180" y="139" width="4" height="9" fill="#C9A24B" />
        <rect x="186" y="139" width="4" height="6" fill="#C9A24B" />
      </g>
      <path d="M121 128 L130 138 L138 140" fill="none" stroke="#3F5A7A" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="138" cy="141" r="3.4" fill="#D6AB86" />
      <circle cx="139" cy="134" r="3.2" fill="#D6AB86" />
      <path className="g-twinkle" d="M266 46 l3 7 l7 3 l-7 3 l-3 7 l-3 -7 l-7 -3 l7 -3 Z" fill="#C9A24B" />
    </ArtFrame>
  )
}

/**
 * The hero art panel with its floating status bar: a dot in the state's tone,
 * one line of status, and one action that jumps to the thing the art is showing.
 */
export type HeroArtState = {
  status?: string
  tone?: "green" | "red" | "amber"
  action?: { label: string; onClick: () => void; disabled?: boolean }
}

export function HeroArt({ art, status, tone, action }: HeroArtState & { art: ReactNode }) {
  return (
    <div className="ov-hero-art">
      {art}
      {status ? (
        <div className="ag-art-bar">
          <span className="ag-art-status" role="status">
            <i className={tone} aria-hidden />
            {status}
          </span>
          {action ? (
            <button type="button" onClick={action.onClick} disabled={action.disabled}>
              {action.label}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
