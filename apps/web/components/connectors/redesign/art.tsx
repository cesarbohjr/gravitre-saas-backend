"use client"

import { useId, type CSSProperties } from "react"
import { COVER_ICONS, coverFor, vendorLook, type CoverSpec } from "./vendor-look"

/** Two-letter vendor tile in the vendor's colours (sizes: sm 28, default 36, md 44, lg 76). */
export function VendorTile({
  vendor,
  category,
  size,
  className,
  style,
}: {
  vendor: string
  category?: string
  size?: "sm" | "md" | "lg"
  className?: string
  style?: CSSProperties
}) {
  const look = vendorLook(vendor, category)
  return (
    <span
      className={["cn-logo", size, className].filter(Boolean).join(" ")}
      style={{ background: look.bg, color: look.fg, ...style }}
      aria-hidden
    >
      {look.mono}
    </span>
  )
}

function svgIds(raw: string) {
  const base = raw.replace(/[^a-zA-Z0-9_-]/g, "")
  return (name: string) => `${base}${name}`
}

const GRAIN = "0 0 0 0 0.15 0 0 0 0 0.13 0 0 0 0 0.1 0.9 0 0 0 -0.38"

/**
 * The connector cover: a soft mesh of three palette colours, a dot grid fading
 * in from the right, line art for the kind of system (a contact card for CRMs,
 * a box for ERPs) and the paper grain. Every connector of a kind shares it.
 */
export function ConnectorCover({ vendor, category, spec }: { vendor?: string; category?: string; spec?: CoverSpec }) {
  const id = svgIds(useId())
  const cover = spec ?? coverFor(vendor ?? "", category)
  const [c0, c1, c2, c3] = cover.colors
  const [big, i1, i2, i3, i4] = cover.icons.map((key) => COVER_ICONS[key])
  return (
    <svg viewBox="0 0 1300 168" preserveAspectRatio="xMaxYMid slice" width="100%" height="100%" aria-hidden className="cn-art">
      <defs>
        <filter id={id("g")} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves={2} stitchTiles="stitch" />
          <feColorMatrix values={GRAIN} />
        </filter>
        <filter id={id("b")} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation={55} />
        </filter>
        <linearGradient id={id("f")} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0.35" stopColor="#FFFFFF" stopOpacity="0" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="1" />
        </linearGradient>
        <pattern id={id("d")} width="16" height="16" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1" fill="#262826" />
        </pattern>
        <mask id={id("m")}>
          <rect width="1300" height="168" fill={`url(#${id("f")})`} />
        </mask>
      </defs>
      <rect width="1300" height="168" fill={c0} />
      <g filter={`url(#${id("b")})`}>
        <circle className="g-drift" cx="260" cy="20" r="210" fill={c1} />
        <circle className="g-drift2" cx="820" cy="190" r="220" fill={c2} opacity="0.8" />
        <circle className="g-drift" cx="1180" cy="10" r="200" fill={c3} style={{ animationDuration: "22s" }} />
      </g>
      <rect width="1300" height="168" fill={`url(#${id("d")})`} opacity="0.2" mask={`url(#${id("m")})`} />
      <g className="g-parallax" fill="none" stroke={cover.stroke} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="720" cy="140" r="9" strokeWidth="4" opacity="0.8" />
        <circle cx="880" cy="20" r="12" strokeWidth="4" opacity="0.8" />
        <circle cx="1172" cy="150" r="16" strokeWidth="4" opacity="0.8" />
        <g transform="translate(600 6) scale(7)" opacity="0.8">
          <path d={i1} strokeWidth="5" vectorEffect="non-scaling-stroke" />
        </g>
        <g transform="translate(776 30) scale(6.5)" opacity="0.8">
          <path d={i2} strokeWidth="5" vectorEffect="non-scaling-stroke" />
        </g>
        <g transform="translate(956 -30) scale(12)">
          <path d={big} strokeWidth="7" vectorEffect="non-scaling-stroke" />
        </g>
        <g transform="translate(1196 6) scale(4)" opacity="0.8">
          <path d={i3} strokeWidth="4" vectorEffect="non-scaling-stroke" />
        </g>
        <g transform="translate(1226 92) scale(5)" opacity="0.8">
          <path d={i4} strokeWidth="4" vectorEffect="non-scaling-stroke" />
        </g>
      </g>
      <rect width="1300" height="168" filter={`url(#${id("g")})`} opacity="0.45" />
    </svg>
  )
}

function Logo({ x, y, scale }: { x: number; y: number; scale: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} fill="#19C37D">
      <path d="M7 0h23l-4 6H3z" />
      <path d="M5 8h22l-4 6H1z" />
      <path d="M3 16h20l-4 6H0z" />
    </g>
  )
}

type TileState = "ok" | "bad" | "empty"

/**
 * Hub hero: a person plugging a cable into the Gravitre hub with three app
 * tiles. Each tile draws a real connector state: green and flowing when it is
 * ready, red and still when it needs attention, a dashed outline when there is
 * no connector for that slot yet.
 */
export function HubHeroArt({ tiles }: { tiles: [TileState, TileState, TileState] }) {
  const id = svgIds(useId())
  const ys = [46, 92, 138]
  const label = `The Gravitre hub with ${tiles.filter((t) => t === "ok").length} ready ${
    tiles.filter((t) => t === "ok").length === 1 ? "system" : "systems"
  }${tiles.includes("bad") ? " and one that needs attention" : ""}`
  return (
    <svg role="img" aria-label={label} viewBox="-10 -50 340 290" preserveAspectRatio="xMidYMid slice" className="cn-art">
      <defs>
        <filter id={id("b")} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation={19} />
        </filter>
        <filter id={id("g")} x="0" y="0" width="100%" height="100%" filterUnits="objectBoundingBox">
          <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves={2} stitchTiles="stitch" />
          <feColorMatrix values={GRAIN} />
        </filter>
      </defs>
      <rect x="-10" y="-50" width="340" height="290" fill="#E7ECE3" />
      <g filter={`url(#${id("b")})`}>
        <circle className="g-mesh" cx="40" cy="20" r="90" fill="#CFDCCB" />
        <ellipse cx="190" cy="100" rx="130" ry="80" fill="#DCE5DC" />
        <circle className="g-mesh" cx="300" cy="10" r="80" fill="#DCE3E8" />
        <circle className="g-mesh" cx="280" cy="200" r="70" fill="#EBDCC0" />
      </g>
      {tiles.map((state, index) => {
        const y = ys[index]
        const d = y === 92 ? "M92 92 L178 92" : `M92 ${y} C130 ${y} 140 92 178 92`
        if (state === "empty") return null
        return (
          <path
            key={`l${index}`}
            d={d}
            fill="none"
            stroke={state === "bad" ? "#A3333D" : "#8A8985"}
            strokeWidth="1.6"
            strokeDasharray="3 5"
            className={state === "ok" ? "g-flow" : undefined}
          />
        )
      })}
      {tiles.map((state, index) => {
        const y = ys[index] - 16
        if (state === "empty") {
          return (
            <rect key={`t${index}`} x="50" y={y} width="42" height="32" rx="8" fill="none" stroke="#8A8985" strokeWidth="1.4" strokeDasharray="3 3" />
          )
        }
        const bad = state === "bad"
        return (
          <g key={`t${index}`} className={index === 1 && !bad ? "g-float" : undefined}>
            <rect x="50" y={y} width="42" height="32" rx="8" fill={bad ? "#F5F2EA" : "#FFFFFF"} stroke={bad ? "#A3333D" : "#2E9E5B"} strokeWidth="1.5" />
            <rect x="60" y={y + 10} width="22" height="4" rx="2" fill={bad ? "#C9C4B8" : "#2B2D31"} />
            <rect x="60" y={y + 19} width="14" height="4" rx="2" fill={bad ? "#E2DED4" : "#C9C4B8"} />
          </g>
        )
      })}
      <rect x="178" y="66" width="56" height="52" rx="12" fill="#141513" />
      <Logo x={188} y={78.8} scale={1.2} />
      {tiles.includes("ok") ? (
        <g className="g-float">
          <circle cx="234" cy="64" r="10" fill="#2E9E5B" stroke="#F5F2EA" strokeWidth="3" />
          <path d="M229.5 64 l3 3 l6 -6" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      ) : null}
      <g transform="translate(272 0)">
        <rect x="-8" y="128" width="7" height="44" rx="3" fill="#26282C" />
        <rect x="1" y="128" width="7" height="44" rx="3" fill="#26282C" />
        <path d="M-13 92 Q0 84 13 92 L15 132 L-15 132 Z" fill="#3F5A7A" />
        <path d="M-9 98 L-22 108 L-34 110" fill="none" stroke="#344C68" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-36" cy="110" r="3.4" fill="#C99572" />
        <circle cx="0" cy="74" r="10" fill="#C99572" />
        <path d="M-10.5 74 A10.5 10.5 0 0 1 10.5 74 Q2 66 -10.5 74 Z" fill="#1F1A17" />
      </g>
      <rect x="232" y="106" width="8" height="8" rx="2" fill="#C9A24B" />
      <path d="M300 30 l2.5 6 l6 2.5 l-6 2.5 l-2.5 6 l-2.5 -6 l-6 -2.5 l6 -2.5 Z" fill="#C9A24B" className="g-twinkle" />
      <line x1="20" y1="172" x2="300" y2="172" stroke="#9C8C74" strokeWidth="2" />
      <rect x="-10" y="-50" width="340" height="290" filter={`url(#${id("g")})`} opacity="0.55" />
    </svg>
  )
}

/** First run: a person carrying a plug toward an empty hub socket. */
export function FirstRunArt() {
  const id = svgIds(useId())
  return (
    <svg role="img" aria-label="A person carrying a plug toward an empty hub socket" viewBox="0 0 320 200" preserveAspectRatio="xMidYMid slice" className="cn-art" style={{ display: "block", width: "100%", height: "100%" }}>
      <defs>
        <filter id={id("b")} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation={19} />
        </filter>
        <filter id={id("g")} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves={2} stitchTiles="stitch" />
          <feColorMatrix values={GRAIN} />
        </filter>
      </defs>
      <rect width="320" height="200" fill="#E7ECE3" />
      <g filter={`url(#${id("b")})`}>
        <circle className="g-mesh" cx="40" cy="20" r="96" fill="#CFDCCB" />
        <ellipse cx="200" cy="100" rx="130" ry="90" fill="#DCE5DC" />
        <circle className="g-mesh" cx="300" cy="10" r="80" fill="#DCE3E8" />
        <circle className="g-mesh" cx="280" cy="210" r="70" fill="#EBDCC0" />
      </g>
      <rect x="196" y="58" width="78" height="72" rx="16" fill="#141513" />
      <Logo x={211} y={76.4} scale={1.6} />
      <rect x="186" y="84" width="12" height="20" rx="3" fill="#F5F2EA" stroke="#8A8985" strokeWidth="1.4" strokeDasharray="3 3" />
      <g transform="translate(108 0)">
        <rect x="-8" y="146" width="7" height="40" rx="3" fill="#26282C" />
        <rect x="1" y="146" width="7" height="40" rx="3" fill="#26282C" />
        <path d="M-13 108 Q0 100 13 108 L15 150 L-15 150 Z" fill="#3F5A7A" />
        <circle cx="0" cy="90" r="10" fill="#D6AB86" />
        <path d="M-10.5 89 A10.5 10.5 0 0 1 10.5 89 Q2 81 -10.5 89 Z" fill="#2E231D" />
        <circle cx="-8" cy="81" r="4.5" fill="#2E231D" />
      </g>
      <g className="g-nudge">
        <path d="M121 114 L134 122 L142 122" fill="none" stroke="#3F5A7A" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <rect x="142" y="112" width="22" height="20" rx="5" fill="#C9A24B" />
        <rect x="164" y="116" width="10" height="3" rx="1.5" fill="#6B5A3A" />
        <rect x="164" y="125" width="10" height="3" rx="1.5" fill="#6B5A3A" />
        <path d="M142 124 C120 150 70 140 60 180" fill="none" stroke="#6B5A3A" strokeWidth="2.4" />
      </g>
      <path className="g-twinkle" d="M290 38 l3 7 l7 3 l-7 3 l-3 7 l-3 -7 l-7 -3 l7 -3 Z" fill="#C9A24B" />
      <line x1="24" y1="186" x2="296" y2="186" stroke="#9C8C74" strokeWidth="2" />
      <rect width="320" height="200" filter={`url(#${id("g")})`} opacity="0.55" />
    </svg>
  )
}

export type StarterDept = "sales" | "marketing" | "finance" | "support" | "operations" | "engineering"

export const STARTER_LOOK: Record<StarterDept, { ink: string; colors: [string, string, string, string]; icon: string }> = {
  sales: { ink: "#5B5BD6", colors: ["#E9E9F3", "#CACCE8", "#E4DDEF", "#D9E3EC"], icon: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10z M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2z" },
  marketing: { ink: "#A5563C", colors: ["#F1EAE0", "#EBDCC0", "#E9CDBF", "#E6E0D2"], icon: COVER_ICONS.mega },
  finance: { ink: "#4E7350", colors: ["#E7ECE3", "#CFDCCB", "#EBDCC0", "#DCE3E8"], icon: COVER_ICONS.calc },
  support: { ink: "#4D6472", colors: ["#E8EBEE", "#D9DEE3", "#D6E2E4", "#E6E2D8"], icon: COVER_ICONS.chat },
  operations: { ink: "#8A5A06", colors: ["#F1ECE0", "#E6D6B6", "#E9E1CC", "#DDE2E3"], icon: COVER_ICONS.gear },
  engineering: { ink: "#2B59E0", colors: ["#E8ECF4", "#CFD9EC", "#DCE2F0", "#E6E2D8"], icon: COVER_ICONS.code },
}

/** The starter-set card art: a soft mesh in the team's colours with a small scene of its work. */
export function StarterSetArt({ dept }: { dept: StarterDept }) {
  const id = svgIds(useId())
  const look = STARTER_LOOK[dept]
  const [c0, c1, c2, c3] = look.colors
  const shadow = `url(#${id("s")})`
  return (
    <svg viewBox="0 0 340 150" preserveAspectRatio="xMidYMid slice" width="100%" height="100%" aria-hidden className="cn-art">
      <defs>
        <filter id={id("g")} x="0" y="0" width="100%" height="100%">
          <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves={2} stitchTiles="stitch" />
          <feColorMatrix values="0 0 0 0 0.15 0 0 0 0 0.13 0 0 0 0 0.1 0.9 0 0 0 -0.4" />
        </filter>
        <filter id={id("s")} x="-20%" y="-20%" width="140%" height="160%">
          <feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="#141513" floodOpacity="0.09" />
        </filter>
        <filter id={id("b")} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation={20} />
        </filter>
        <pattern id={id("d")} width="9" height="9" patternUnits="userSpaceOnUse">
          <circle cx="1.5" cy="1.5" r="0.7" fill="#262826" />
        </pattern>
        <linearGradient id={id("f")} x1="0" x2="1" y1="0" y2="0">
          <stop offset="0.35" stopColor="#FFFFFF" stopOpacity="0" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="1" />
        </linearGradient>
        <mask id={id("m")}>
          <rect width="340" height="150" fill={`url(#${id("f")})`} />
        </mask>
      </defs>
      <rect width="340" height="150" fill={c0} />
      <g filter={`url(#${id("b")})`}>
        <circle className="g-drift" cx="70" cy="10" r="78" fill={c1} />
        <circle className="g-drift" cx="200" cy="160" r="84" fill={c2} opacity="0.8" style={{ animationDelay: "-5s" }} />
        <circle className="g-drift" cx="320" cy="4" r="74" fill={c3} style={{ animationDelay: "-9s" }} />
      </g>
      <rect width="340" height="150" fill={`url(#${id("d")})`} opacity="0.2" mask={`url(#${id("m")})`} />
      <rect width="340" height="150" filter={`url(#${id("g")})`} opacity="0.45" />
      {dept === "sales" ? (
        <g>
          <g filter={shadow}><rect x="58" y="18" width="224" height="114" rx="11" fill="#FFFFFF" stroke="#E4E4DF" /></g>
          <rect x="70" y="30" width="30" height="5" rx="2.5" fill="#262826" />
          <rect x="140" y="30" width="30" height="5" rx="2.5" fill="#262826" />
          <rect x="210" y="30" width="30" height="5" rx="2.5" fill="#262826" />
          {[44, 72, 100].map((y) => <rect key={`a${y}`} x="68" y={y} width="62" height="22" rx="6" fill="#F4F4FA" stroke="#E4E4DF" />)}
          {[44, 72].map((y) => <rect key={`b${y}`} x="138" y={y} width="62" height="22" rx="6" fill="#F4F4FA" stroke="#E4E4DF" />)}
          <rect x="208" y="44" width="62" height="22" rx="6" fill="#EEEEFB" stroke="#CACCE8" />
          <rect x="74" y="52" width="30" height="4" rx="2" fill="#CBCBC3" />
          <rect x="74" y="80" width="38" height="4" rx="2" fill="#CBCBC3" />
          <rect x="74" y="108" width="26" height="4" rx="2" fill="#CBCBC3" />
          <rect x="144" y="52" width="34" height="4" rx="2" fill="#CBCBC3" />
          <rect x="144" y="80" width="28" height="4" rx="2" fill="#CBCBC3" />
          <rect x="214" y="52" width="32" height="4" rx="2" fill="#5B5BD6" />
          <path className="g-flow" d="M200 92 C214 92 222 84 226 76" fill="none" stroke="#5B5BD6" strokeWidth="2" strokeDasharray="3 4" />
          <g className="g-float">
            <rect x="196" y="82" width="66" height="26" rx="7" fill="#FFFFFF" stroke="#5B5BD6" strokeWidth="1.5" filter={shadow} />
            <circle cx="208" cy="95" r="5" fill="#5B5BD6" />
            <rect x="218" y="90" width="34" height="4" rx="2" fill="#262826" />
            <rect x="218" y="98" width="22" height="3.5" rx="1.75" fill="#CBCBC3" />
          </g>
        </g>
      ) : dept === "marketing" ? (
        <g>
          <g filter={shadow}><rect x="52" y="22" width="160" height="104" rx="11" fill="#FFFFFF" stroke="#E4E4DF" /></g>
          <rect x="64" y="34" width="44" height="5" rx="2.5" fill="#262826" />
          <path d="M64 60h136M64 82h136M64 104h136" stroke="#EFEFEA" strokeWidth="1" />
          <path d="M64 110 L90 100 L112 104 L138 82 L162 86 L196 52 L196 114 L64 114 Z" fill="#F3E3DA" />
          <path d="M64 110 L90 100 L112 104 L138 82 L162 86 L196 52" fill="none" stroke="#A5563C" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
          <circle className="g-twinkle" cx="196" cy="52" r="4" fill="#A5563C" />
          <g className="g-float">
            <rect x="186" y="56" width="104" height="66" rx="10" fill="#FFFFFF" stroke="#E4E4DF" filter={shadow} />
            <circle cx="202" cy="72" r="6" fill="none" stroke="#A5563C" strokeWidth="2.2" />
            <path d="M206.5 76.5l4 4" stroke="#A5563C" strokeWidth="2.2" strokeLinecap="round" />
            <rect x="216" y="69" width="44" height="5" rx="2.5" fill="#262826" />
            <rect x="198" y="90" width="58" height="4" rx="2" fill="#CBCBC3" />
            <path d="M270 94l4-5 4 5" fill="none" stroke="#19C37D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <rect x="198" y="104" width="46" height="4" rx="2" fill="#CBCBC3" />
            <path d="M270 108l4-5 4 5" fill="none" stroke="#19C37D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        </g>
      ) : dept === "finance" ? (
        <g>
          <g filter={shadow}><path d="M96 14h112v118l-14-7-14 7-14-7-14 7-14-7-14 7-14-7-14 7z" fill="#FFFFFF" stroke="#E4E4DF" /></g>
          <rect x="108" y="26" width="40" height="6" rx="3" fill="#262826" />
          <rect x="108" y="38" width="26" height="4" rx="2" fill="#CBCBC3" />
          <path d="M108 54h88M108 70h88M108 86h88" stroke="#EFEFEA" strokeWidth="1" />
          <rect x="108" y="58" width="44" height="4" rx="2" fill="#CBCBC3" />
          <rect x="178" y="58" width="18" height="4" rx="2" fill="#CBCBC3" />
          <rect x="108" y="74" width="36" height="4" rx="2" fill="#CBCBC3" />
          <rect x="178" y="74" width="18" height="4" rx="2" fill="#CBCBC3" />
          <rect x="108" y="96" width="30" height="6" rx="3" fill="#4E7350" />
          <rect x="168" y="96" width="28" height="6" rx="3" fill="#262826" />
          <g>
            <circle cx="222" cy="98" r="20" fill="#FFFFFF" stroke="#4E7350" strokeWidth="2.4" strokeDasharray="4 3" />
            <path d="M213 98l6 6 11-12" fill="none" stroke="#4E7350" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </g>
          <g className="g-float">
            <ellipse cx="262" cy="118" rx="18" ry="6" fill="#E9D49A" stroke="#C9A24B" strokeWidth="1.5" />
            <ellipse cx="262" cy="110" rx="18" ry="6" fill="#EFDDA9" stroke="#C9A24B" strokeWidth="1.5" />
            <ellipse cx="262" cy="102" rx="18" ry="6" fill="#F5E6BC" stroke="#C9A24B" strokeWidth="1.5" />
          </g>
        </g>
      ) : dept === "support" ? (
        <g>
          <g filter={shadow}><rect x="66" y="16" width="208" height="118" rx="12" fill="#FFFFFF" stroke="#E4E4DF" /></g>
          <rect x="78" y="27" width="40" height="5" rx="2.5" fill="#262826" />
          <rect x="226" y="24" width="38" height="12" rx="6" fill="#E3EAEE" />
          <rect x="232" y="28.5" width="26" height="3" rx="1.5" fill="#4D6472" />
          <rect x="78" y="44" width="96" height="22" rx="10" fill="#F1F1EC" />
          <rect x="86" y="50" width="70" height="4" rx="2" fill="#CBCBC3" />
          <rect x="86" y="57" width="48" height="4" rx="2" fill="#CBCBC3" />
          <rect x="150" y="72" width="112" height="22" rx="10" fill="#4D6472" />
          <rect x="158" y="78" width="82" height="4" rx="2" fill="#FFFFFF" opacity=".85" />
          <rect x="158" y="85" width="56" height="4" rx="2" fill="#FFFFFF" opacity=".6" />
          <rect x="78" y="102" width="44" height="20" rx="10" fill="#F1F1EC" />
          {[90, 100, 110].map((cx, index) => (
            <circle key={cx} className="g-twinkle" cx={cx} cy="112" r="2.6" fill="#8A8B85" style={{ animationDelay: `${index * 0.3}s` }} />
          ))}
        </g>
      ) : dept === "operations" ? (
        <g>
          <g filter={shadow}><rect x="50" y="22" width="236" height="104" rx="11" fill="#FFFFFF" stroke="#E4E4DF" /></g>
          <rect x="62" y="34" width="44" height="5" rx="2.5" fill="#262826" />
          <path d="M110 48v70M150 48v70M190 48v70M230 48v70M270 48v70" stroke="#EFEFEA" strokeWidth="1" />
          <rect x="62" y="56" width="34" height="4" rx="2" fill="#CBCBC3" />
          <rect x="62" y="76" width="28" height="4" rx="2" fill="#CBCBC3" />
          <rect x="62" y="96" width="38" height="4" rx="2" fill="#CBCBC3" />
          <rect x="112" y="52" width="70" height="12" rx="6" fill="#E6D6B6" />
          <rect x="150" y="72" width="96" height="12" rx="6" fill="#8A5A06" />
          <rect x="196" y="92" width="62" height="12" rx="6" fill="#E9C77A" />
          <path d="M214 46v74" stroke="#19C37D" strokeWidth="2" strokeDasharray="3 3" />
          <circle cx="214" cy="46" r="3.5" fill="#19C37D" />
        </g>
      ) : (
        <g>
          <g filter={shadow}><rect x="56" y="18" width="228" height="114" rx="11" fill="#141513" stroke="#262826" /></g>
          <circle cx="70" cy="30" r="3" fill="#A3333D" />
          <circle cx="80" cy="30" r="3" fill="#E2A33A" />
          <circle cx="90" cy="30" r="3" fill="#19C37D" />
          <path d="M70 52l8 6-8 6" fill="none" stroke="#19C37D" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          <rect x="86" y="56" width="86" height="4" rx="2" fill="#CFD9EC" />
          <rect x="70" y="74" width="120" height="4" rx="2" fill="#5A6B8F" />
          <rect x="70" y="86" width="96" height="4" rx="2" fill="#5A6B8F" />
          <rect x="70" y="98" width="70" height="4" rx="2" fill="#2B59E0" />
          <rect className="g-twinkle" x="146" y="96" width="7" height="9" rx="1" fill="#19C37D" />
          <g className="g-float">
            <rect x="200" y="62" width="96" height="58" rx="10" fill="#FFFFFF" stroke="#E4E4DF" filter={shadow} />
            <circle cx="216" cy="78" r="4" fill="none" stroke="#2B59E0" strokeWidth="2" />
            <circle cx="216" cy="104" r="4" fill="none" stroke="#2B59E0" strokeWidth="2" />
            <path d="M216 82v18 M216 90 C230 90 236 84 244 80" fill="none" stroke="#2B59E0" strokeWidth="2" />
            <rect x="250" y="76" width="34" height="4" rx="2" fill="#262826" />
            <rect x="230" y="102" width="44" height="4" rx="2" fill="#CBCBC3" />
          </g>
        </g>
      )}
    </svg>
  )
}

/** The round white icon badge beside a starter set's title. */
export function StarterSetIcon({ dept }: { dept: StarterDept }) {
  const look = STARTER_LOOK[dept]
  return (
    <span
      aria-hidden
      style={{
        flex: "0 0 auto",
        width: 44,
        height: 44,
        borderRadius: "50%",
        display: "grid",
        placeItems: "center",
        background: "#FFFFFF",
        color: look.ink,
        boxShadow: "rgba(20,21,19,0.1) 0 2px 8px, #E4E4DF 0 0 0 1px",
      }}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <path d={look.icon} />
      </svg>
    </span>
  )
}
