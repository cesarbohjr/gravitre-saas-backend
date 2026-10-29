import React, { useId } from "react"
import { cn } from "@/lib/utils"

/**
 * Home-only animated scenes, drawn inline so each part can move on its own.
 * Same vocabulary as public/illustrations (sage wash, soft blobs, dot field,
 * paper cards, ink and copper accents) but unique to the homepage and free of
 * people. Motion lives in globals.css (mk-hs-*) and stops under reduced motion,
 * where every scene falls back to a sensible still frame.
 */

const INK = "#2A2B28"
const PAPER = "#FBF8F2"
const EDGE = "#D9D1C2"
const RULE = "#B3A894"
const GREEN = "#19C37D"
const AMBER = "#E2A33A"

function useSvgId(prefix: string) {
  return `${prefix}${useId().replace(/[^a-zA-Z0-9]/g, "")}`
}

/** Wash, blobs, dot field and grain shared by every scene. */
function Backdrop({ id, w, h, blobs }: { id: string; w: number; h: number; blobs: React.ReactNode }) {
  return (
    <>
      <defs>
        <filter id={`${id}b`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="22" />
        </filter>
        <pattern id={`${id}d`} width="9" height="9" patternUnits="userSpaceOnUse">
          <circle cx="1.8" cy="1.8" r="1" fill={INK} />
        </pattern>
        <linearGradient id={`${id}f`} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0.25" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#fff" stopOpacity="1" />
        </linearGradient>
        <mask id={`${id}m`}>
          <rect width={w} height={h} fill={`url(#${id}f)`} />
        </mask>
        <filter id={`${id}g`} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="1.05" numOctaves="2" seed="7" stitchTiles="stitch" result="n" />
          <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.16  0 0 0 0 0.14  0 0 0 0 0.11  0 0 0 1.5 -0.92" />
          <feComposite in2="SourceAlpha" operator="in" />
        </filter>
      </defs>
      <rect width={w} height={h} fill="#E7ECE3" />
      <g filter={`url(#${id}b)`}>{blobs}</g>
      <rect width={w} height={h} fill={`url(#${id}d)`} opacity="0.18" mask={`url(#${id}m)`} />
    </>
  )
}

function Grain({ id, w, h }: { id: string; w: number; h: number }) {
  return <rect width={w} height={h} filter={`url(#${id}g)`} opacity="0.55" pointerEvents="none" />
}

function Frame({ className, label, children }: { className?: string; label: string; children: React.ReactNode }) {
  return (
    <figure
      className={cn("relative overflow-hidden rounded-2xl border border-divide bg-[#e7ece3]", className)}
      role="img"
      aria-label={label}
    >
      {children}
    </figure>
  )
}

/** Small paper card with an icon dot and two text bars. */
function MiniCard({ x, y, w = 120, h = 52, color }: { x: number; y: number; w?: number; h?: number; color: string }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect width={w} height={h} rx="8" fill={PAPER} stroke={EDGE} strokeWidth="1.5" />
      <rect x="10" y={h / 2 - 11} width="22" height="22" rx="6" fill={color} opacity="0.18" />
      <circle cx="21" cy={h / 2} r="5" fill={color} />
      <rect x="40" y={h / 2 - 8} width={w * 0.42} height="5" rx="2.5" fill={INK} />
      <rect x="40" y={h / 2 + 3} width={w * 0.3} height="4" rx="2" fill={EDGE} />
    </g>
  )
}

/* ------------------------------------------------------------------------ */
/* 1. One brain — departments wired to a shared hub, signals moving both ways */
/* ------------------------------------------------------------------------ */

const HUB = { x: 480, y: 150 }
const DEPARTMENTS = [
  { x: 96, y: 40, color: "#C98F5B", dir: "out" },
  { x: 56, y: 124, color: GREEN, dir: "in" },
  { x: 96, y: 208, color: "#5B6E7A", dir: "out" },
  { x: 744, y: 40, color: "#B5654A", dir: "in" },
  { x: 784, y: 124, color: AMBER, dir: "out" },
  { x: 744, y: 208, color: "#7E9A7B", dir: "in" },
] as const

function wire(d: (typeof DEPARTMENTS)[number]) {
  const left = d.x < HUB.x
  const sx = left ? d.x + 120 : d.x
  const sy = d.y + 26
  const ex = left ? HUB.x - 48 : HUB.x + 48
  const mid = (sx + ex) / 2
  return `M${ex} ${HUB.y} C${mid} ${HUB.y} ${mid} ${sy} ${sx} ${sy}`
}

export function OneBrainScene({ className }: { className?: string }) {
  const id = useSvgId("hb")
  const W = 960
  const H = 300
  return (
    <Frame className={className} label="Six departments connected to one shared Gravitre brain, with work moving between them">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" aria-hidden>
        <Backdrop
          id={id}
          w={W}
          h={H}
          blobs={
            <>
              <circle className="mk-hs-blob" cx="120" cy="40" r="120" fill="#CFDCCB" opacity="0.9" />
              <ellipse cx="480" cy="160" rx="260" ry="110" fill="#DCE3D3" />
              <circle className="mk-hs-blob" style={{ animationDelay: "-6s" }} cx="860" cy="30" r="110" fill="#DCE3E8" />
              <circle className="mk-hs-blob" style={{ animationDelay: "-11s" }} cx="820" cy="300" r="100" fill="#EBDCC0" opacity="0.8" />
            </>
          }
        />
        {DEPARTMENTS.map((d, i) => (
          <g key={i}>
            <path d={wire(d)} fill="none" stroke={RULE} strokeWidth="1.5" strokeDasharray="3 5" strokeLinecap="round" />
            <path
              d={wire(d)}
              pathLength={100}
              fill="none"
              stroke={GREEN}
              strokeWidth="3"
              strokeLinecap="round"
              className={d.dir === "in" ? "mk-hs-signal mk-hs-signal-in" : "mk-hs-signal"}
              style={{ animationDelay: `${-i * 0.55}s` }}
            />
          </g>
        ))}
        {/* hub */}
        <circle className="mk-hs-ring" cx={HUB.x} cy={HUB.y} r="64" fill="none" stroke={GREEN} strokeWidth="1.5" />
        <circle className="mk-hs-ring" style={{ animationDelay: "-1.6s" }} cx={HUB.x} cy={HUB.y} r="64" fill="none" stroke={GREEN} strokeWidth="1.5" />
        <rect x={HUB.x - 48} y={HUB.y - 48} width="96" height="96" rx="22" fill={INK} />
        <rect x={HUB.x - 48} y={HUB.y - 48} width="96" height="48" rx="22" fill="#fff" opacity="0.05" />
        <path d={`M${HUB.x - 22} ${HUB.y - 16} h40 l-8 12 h-40 z`} fill={GREEN} />
        <path d={`M${HUB.x - 14} ${HUB.y + 4} h40 l-8 12 h-40 z`} fill={GREEN} opacity="0.75" />
        {/* departments */}
        {DEPARTMENTS.map((d, i) => (
          <g key={i} className="mk-hs-bob" style={{ animationDelay: `${-i * 1.1}s` }}>
            <MiniCard x={d.x} y={d.y} color={d.color} />
            <circle
              className="mk-hs-blink"
              style={{ animationDelay: `${-i * 0.55}s` }}
              cx={d.x + 108}
              cy={d.y + 12}
              r="3.5"
              fill={GREEN}
            />
          </g>
        ))}
        <Grain id={id} w={W} h={H} />
      </svg>
    </Frame>
  )
}

/* ------------------------------------------------------------------------ */
/* 2. Approval gate — tasks roll up to a gate, get approved, land in the log */
/* ------------------------------------------------------------------------ */

const GATE_TASKS = [
  { color: "#C98F5B", delay: 0, rest: 208, approved: true },
  { color: "#5B6E7A", delay: -3, rest: 70, approved: false },
  { color: "#B5654A", delay: -6, rest: 360, approved: true },
]

export function ApprovalGateScene({ className }: { className?: string }) {
  const id = useSvgId("ag")
  const W = 480
  const H = 300
  return (
    <Frame className={className} label="Tasks pause at an approval gate, get approved, and are written to the audit log">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" aria-hidden>
        <Backdrop
          id={id}
          w={W}
          h={H}
          blobs={
            <>
              <circle className="mk-hs-blob" cx="60" cy="40" r="110" fill="#CFDCCB" opacity="0.9" />
              <ellipse cx="240" cy="190" rx="200" ry="90" fill="#DCE3D3" />
              <circle className="mk-hs-blob" style={{ animationDelay: "-8s" }} cx="450" cy="40" r="90" fill="#EBDCC0" opacity="0.8" />
            </>
          }
        />
        {/* audit log */}
        <g transform="translate(330 34)">
          <rect width="118" height="96" rx="8" fill={PAPER} stroke={EDGE} strokeWidth="1.5" />
          <rect x="12" y="12" width="44" height="5" rx="2.5" fill={INK} />
          {[0, 1, 2, 3].map((r) => (
            <g key={r} transform={`translate(12 ${30 + r * 15})`}>
              <circle cx="3" cy="3" r="3" fill={GREEN} />
              <rect
                className="mk-hs-logline"
                style={{ animationDelay: `${-r * 0.75}s` }}
                x="12"
                y="1"
                width={[70, 58, 76, 50][r]}
                height="4"
                rx="2"
                fill={EDGE}
              />
            </g>
          ))}
        </g>
        {/* policy tag */}
        <g className="mk-hs-bob">
          <g transform="translate(34 46)">
            <rect width="104" height="40" rx="8" fill={PAPER} stroke={EDGE} strokeWidth="1.5" />
            <path d="M14 12 l9 -4 l9 4 v7 c0 6 -4 9 -9 11 c-5 -2 -9 -5 -9 -11 z" fill={GREEN} opacity="0.85" />
            <rect x="40" y="14" width="48" height="5" rx="2.5" fill={INK} />
            <rect x="40" y="23" width="34" height="4" rx="2" fill={EDGE} />
          </g>
        </g>
        {/* rail */}
        <path d="M18 262 H462" stroke={RULE} strokeWidth="1.5" strokeLinecap="round" />
        <rect x="18" y="226" width="444" height="14" rx="3" fill="#5B6E7A" />
        <rect x="18" y="229" width="444" height="3" fill="#D9DEE3" opacity=".5" />
        {[60, 130, 200, 270, 340, 410].map((x) => (
          <circle key={x} cx={x} cy="233" r="3" fill="#C98F5B" />
        ))}
        {/* tasks */}
        {GATE_TASKS.map((t, i) => (
          <g
            key={i}
            className="mk-hs-task"
            style={{ animationDelay: `${t.delay}s`, ["--rest" as string]: `${t.rest}px` }}
          >
            <rect x="0" y="174" width="64" height="48" rx="8" fill={PAPER} stroke={EDGE} strokeWidth="1.5" />
            <circle cx="15" cy="190" r="5" fill={t.color} />
            <rect x="25" y="187" width="28" height="5" rx="2.5" fill={INK} />
            <rect x="11" y="201" width="40" height="4" rx="2" fill={EDGE} />
            <rect x="11" y="209" width="30" height="4" rx="2" fill={EDGE} />
            <g
              className="mk-hs-stamp"
              style={{ animationDelay: `${t.delay}s`, ["--rest-o" as string]: t.approved ? 1 : 0 }}
            >
              <circle cx="56" cy="176" r="10" fill={GREEN} />
              <path d="M51 176 l3.5 3.5 l6.5 -7" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            </g>
          </g>
        ))}
        {/* gate (drawn over the tasks so they pass through it) */}
        <rect x="196" y="120" width="10" height="110" rx="3" fill={INK} />
        <rect x="282" y="120" width="10" height="110" rx="3" fill={INK} />
        <rect x="190" y="104" width="108" height="28" rx="8" fill={INK} />
        <circle cx="222" cy="118" r="6" fill={AMBER} />
        <circle className="mk-hs-go" cx="222" cy="118" r="6" fill={GREEN} />
        <rect x="236" y="114" width="46" height="8" rx="4" fill="#fff" opacity="0.18" />
        <Grain id={id} w={W} h={H} />
      </svg>
    </Frame>
  )
}

/* ------------------------------------------------------------------------ */
/* 3. Honest pricing — a receipt prints line by line and checks out clean    */
/* ------------------------------------------------------------------------ */

export function ReceiptScene({ className }: { className?: string }) {
  const id = useSvgId("rc")
  const W = 480
  const H = 300
  const zig = Array.from({ length: 12 }, () => "l-6 6 l-6 -6").join(" ")
  return (
    <Frame className={className} label="A short, itemised receipt printing with nothing hidden">
      <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" aria-hidden>
        <Backdrop
          id={id}
          w={W}
          h={H}
          blobs={
            <>
              <circle className="mk-hs-blob" cx="420" cy="50" r="110" fill="#DCE3E8" />
              <ellipse cx="240" cy="190" rx="200" ry="90" fill="#DCE3D3" />
              <circle className="mk-hs-blob" style={{ animationDelay: "-9s" }} cx="40" cy="280" r="100" fill="#EBDCC0" opacity="0.8" />
            </>
          }
        />
        <defs>
          <clipPath id={`${id}c`}>
            <rect x="150" y="78" width="180" height="210" />
          </clipPath>
        </defs>
        {/* plan toggle */}
        <g className="mk-hs-bob">
          <g transform="translate(34 60)">
            <rect width="96" height="40" rx="8" fill={PAPER} stroke={EDGE} strokeWidth="1.5" />
            <rect x="12" y="12" width="40" height="16" rx="8" fill="#E7ECE3" stroke={EDGE} />
            <circle className="mk-hs-knob" cx="20" cy="20" r="6" fill={GREEN} />
            <rect x="60" y="17" width="24" height="6" rx="3" fill={INK} />
          </g>
        </g>
        {/* price tag */}
        <g transform="translate(372 172)">
          <g className="mk-hs-swing">
            <path d="M18 -26 V0" stroke={RULE} strokeWidth="1.5" />
            <path d="M0 6 l18 -10 l18 10 v40 a6 6 0 0 1 -6 6 h-24 a6 6 0 0 1 -6 -6 z" fill={PAPER} stroke={EDGE} strokeWidth="1.5" />
            <circle cx="18" cy="8" r="3" fill={EDGE} />
            <rect x="8" y="22" width="20" height="6" rx="3" fill={INK} />
            <rect x="11" y="33" width="14" height="4" rx="2" fill={EDGE} />
          </g>
        </g>
        {/* receipt */}
        <g clipPath={`url(#${id}c)`}>
          <g className="mk-hs-print">
            <path d={`M168 80 h144 v170 ${zig} z`} fill="#fff" stroke={EDGE} strokeWidth="1.5" />
            {[0, 1, 2].map((r) => (
              <g key={r} transform={`translate(184 ${108 + r * 24})`}>
                <rect width={[62, 48, 70][r]} height="5" rx="2.5" fill={INK} opacity="0.85" />
                <rect x="88" width="24" height="5" rx="2.5" fill={EDGE} />
              </g>
            ))}
            <path d="M184 184 H296" stroke={EDGE} strokeWidth="1.5" strokeDasharray="4 4" />
            <rect x="184" y="198" width="40" height="7" rx="3.5" fill={INK} />
            <rect x="262" y="198" width="34" height="7" rx="3.5" fill={INK} />
            <g className="mk-hs-paid">
              <circle cx="240" cy="230" r="11" fill={GREEN} />
              <path d="M234.5 230 l3.8 3.8 l7 -7.6" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
            </g>
          </g>
        </g>
        {/* printer */}
        <rect x="140" y="44" width="200" height="44" rx="12" fill={INK} />
        <rect x="158" y="74" width="164" height="6" rx="3" fill="#000" opacity="0.45" />
        <circle className="mk-hs-blink" cx="318" cy="58" r="4" fill={GREEN} />
        <rect x="160" y="55" width="54" height="6" rx="3" fill="#fff" opacity="0.18" />
        <Grain id={id} w={W} h={H} />
      </svg>
    </Frame>
  )
}
