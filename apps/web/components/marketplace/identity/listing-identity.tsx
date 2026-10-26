"use client"

import { useId, type CSSProperties, type ReactNode } from "react"
import { cn } from "@/lib/utils"
import {
  COVER_RINGS,
  LISTING_KINDS,
  identityDepartmentFor,
  type IdentityDepartment,
  type ListingKind,
} from "@/lib/listing-identity"
import "./listing-identity.css"

/** A 24x24 stroke icon from the identity system. */
export function IdentityIcon({ d, size = 20, className }: { d: string; size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
    >
      <path d={d} />
    </svg>
  )
}

/**
 * The white circle badge: its icon says what the listing is, its color says
 * which team it serves. Agents wear their department icon, the default avatar
 * for every AI agent.
 */
export function ListingBadge({
  department,
  kind,
  size = 44,
  className,
  children,
}: {
  department: string | null | undefined | IdentityDepartment
  kind: ListingKind
  size?: number
  className?: string
  children?: ReactNode
}) {
  const dept = typeof department === "object" && department ? department : identityDepartmentFor(department as string | null)
  const icon = kind === "agent" ? dept.icon : LISTING_KINDS[kind].icon
  return (
    <span
      aria-hidden
      className={cn("li-badge", className)}
      data-dept={dept.id}
      style={{ width: size, height: size, color: dept.color } as CSSProperties}
    >
      <IdentityIcon d={icon} size={Math.round(size * 0.45)} />
      {children}
    </span>
  )
}

/** Ids inside an inline SVG must be unique per instance, and useId's colons are not valid in url(#...). */
function useSvgId(prefix: string): string {
  return `${prefix}${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`
}

const INK = "#141513"
const RULE = "#E4E4DF"
const LINE = "#CBCBC3"
const GLOW = "#19C37D"

function CoverScene({ kind, accent, shadow }: { kind: ListingKind; accent: string; shadow: string }) {
  const lift = `url(#${shadow})`
  switch (kind) {
    case "agent":
      return (
        <>
          <g className="li-float">
            <rect x="78" y="24" width="170" height="102" rx="9" fill="#FFFFFF" stroke={RULE} filter={lift} />
            <rect x="90" y="35" width="40" height="5" rx="2.5" fill={LINE} />
            <rect x="90" y="46" width="52" height="11" rx="3" fill={INK} />
            <path d="M90 70H236M90 88H236M90 106H236" stroke="#EFEFEA" />
            <path className="li-pulse" d="M176 76 L204 66 L236 54 L236 74 L204 84 L176 86 Z" fill={accent} opacity=".14" />
            <path className="li-draw" d="M90 104 L108 98 L126 100 L144 90 L160 88 L176 81" fill="none" stroke={accent} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
            <path className="li-flow" d="M176 81 L204 75 L236 64" fill="none" stroke={accent} strokeWidth="2.6" strokeDasharray="4 3" strokeLinecap="round" />
            <circle className="li-ring" cx="176" cy="81" r="4" fill="none" stroke={accent} strokeWidth="1.5" />
            <circle cx="176" cy="81" r="4" fill="#FFFFFF" stroke={accent} strokeWidth="2.4" />
          </g>
          <g className="li-chip">
            <rect x="210" y="96" width="86" height="34" rx="8" fill="#FFFFFF" stroke={RULE} filter={lift} />
            <rect x="220" y="104" width="34" height="4" rx="2" fill={LINE} />
            <rect x="220" y="112" width="22" height="7" rx="3.5" fill={INK} />
            <rect x="262" y="107" width="26" height="12" rx="6" fill="#DDF3E8" />
            <path className="li-pulse" d="M269 115l4-4 4 4" fill="none" stroke="#0B8A5C" strokeWidth="2" strokeLinecap="round" />
          </g>
        </>
      )
    case "workflow":
      return (
        <>
          <path className="li-flow" d="M126 70 H150 M200 70 H224" stroke={accent} strokeWidth="2" strokeDasharray="3 4" />
          <g filter={lift}>
            <rect x="76" y="48" width="52" height="44" rx="10" fill="#FFFFFF" stroke={RULE} />
            <rect x="150" y="48" width="52" height="44" rx="10" fill="#FFFFFF" stroke={RULE} />
          </g>
          <g className="li-pulse">
            <circle cx="99" cy="66" r="7" fill="none" stroke={accent} strokeWidth="2.4" />
            <path d="M104 71l5 5" stroke={accent} strokeWidth="2.4" strokeLinecap="round" />
          </g>
          <rect x="88" y="80" width="28" height="4" rx="2" fill={LINE} />
          <path d="M164 60h24l-9 10v8l-6 3v-11z" fill={accent} opacity=".85" />
          <rect x="162" y="82" width="28" height="4" rx="2" fill={LINE} />
          <g className="li-float">
            <rect x="224" y="40" width="66" height="72" rx="10" fill="#FFFFFF" stroke={RULE} filter={lift} />
            <rect x="234" y="50" width="30" height="5" rx="2.5" fill="#262826" />
            <circle cx="238" cy="66" r="3.5" fill={GLOW} />
            <rect x="246" y="64" width="34" height="4" rx="2" fill={LINE} />
            <circle cx="238" cy="78" r="3.5" fill={GLOW} />
            <rect x="246" y="76" width="28" height="4" rx="2" fill={LINE} />
            <circle className="li-pop" cx="238" cy="90" r="3.5" fill={GLOW} />
            <rect x="246" y="88" width="32" height="4" rx="2" fill={LINE} />
            <circle cx="238" cy="102" r="3.5" fill={RULE} />
            <rect x="246" y="100" width="22" height="4" rx="2" fill={RULE} />
          </g>
          <g className="li-chip">
            <rect x="76" y="104" width="52" height="16" rx="8" fill={INK} />
            <path className="li-pulse" d="M90 108l6 4-6 4z" fill={GLOW} />
            <rect x="100" y="110" width="20" height="4" rx="2" fill="#FFFFFF" opacity=".8" />
          </g>
        </>
      )
    case "knowledge":
      return (
        <>
          <rect x="128" y="26" width="108" height="112" rx="8" fill="#FFFFFF" stroke={RULE} transform="rotate(5 182 82)" />
          <g className="li-float">
            <rect x="112" y="22" width="108" height="112" rx="8" fill="#FFFFFF" stroke={RULE} filter={lift} />
            <rect x="124" y="34" width="50" height="7" rx="3.5" fill="#262826" />
            <rect x="124" y="50" width="84" height="4" rx="2" fill={LINE} />
            <rect x="124" y="58" width="72" height="4" rx="2" fill={LINE} />
            <rect x="122" y="66" width="56" height="10" rx="3" fill="#DDF3E8" />
            <rect className="li-fill" x="126" y="69" width="44" height="4" rx="2" fill="#0B8A5C" />
            <g className="li-pop">
              <circle cx="196" cy="71" r="6" fill="#0B8A5C" />
              <path d="M193.5 71l2 2 3.5-4" fill="none" stroke="#FFFFFF" strokeWidth="1.6" />
            </g>
            <rect x="122" y="82" width="50" height="10" rx="3" fill="#F8E4E6" />
            <path className="li-draw" d="M126 87H166" stroke="#A3333D" strokeWidth="2" />
            <g className="li-pop" style={{ animationDelay: "0.8s" }}>
              <circle cx="196" cy="87" r="6" fill="#A3333D" />
              <path d="M193.5 84.5l5 5M198.5 84.5l-5 5" stroke="#FFFFFF" strokeWidth="1.6" />
            </g>
            <rect x="124" y="100" width="80" height="4" rx="2" fill={LINE} />
            <rect x="124" y="108" width="64" height="4" rx="2" fill={LINE} />
          </g>
          <g className="li-chip">
            <rect x="72" y="40" width="44" height="44" rx="10" fill={INK} filter={lift} />
            <path className="li-pulse" d="M84 70c0-8 3-12 9-14v4c-3 1-4 3-4 5h4v8h-9zM98 70c0-8 3-12 9-14v4c-3 1-4 3-4 5h4v8h-9z" fill={GLOW} />
          </g>
        </>
      )
    case "pack":
      return (
        <>
          <g className="li-float">
            <rect x="84" y="22" width="156" height="104" rx="9" fill="#FFFFFF" stroke={RULE} filter={lift} />
            <rect x="96" y="33" width="44" height="6" rx="3" fill="#262826" />
            <circle cx="102" cy="58" r="6" fill={accent} />
            <rect x="114" y="53" width="64" height="4" rx="2" fill="#262826" opacity=".75" />
            <rect x="114" y="60" width="44" height="3.5" rx="1.75" fill={LINE} />
            <rect className="li-pulse" x="204" y="53" width="24" height="10" rx="5" fill="#F8E4E6" />
            <rect x="209" y="57" width="14" height="2.5" rx="1.25" fill="#A3333D" />
            <path d="M92 72H232" stroke="#EFEFEA" />
            <circle cx="102" cy="85" r="6" fill={accent} opacity=".7" />
            <rect x="114" y="80" width="56" height="4" rx="2" fill="#262826" opacity=".75" />
            <rect x="114" y="87" width="38" height="3.5" rx="1.75" fill={LINE} />
            <rect x="204" y="80" width="24" height="10" rx="5" fill="#FBF1DC" />
            <rect x="209" y="84" width="14" height="2.5" rx="1.25" fill="#8A5A06" />
            <path d="M92 99H232" stroke="#EFEFEA" />
            <circle cx="102" cy="112" r="6" fill={accent} opacity=".45" />
            <rect x="114" y="107" width="60" height="4" rx="2" fill="#262826" opacity=".75" />
            <rect x="114" y="114" width="30" height="3.5" rx="1.75" fill={LINE} />
            <rect x="204" y="107" width="24" height="10" rx="5" fill="#DDF3E8" />
            <rect x="209" y="111" width="14" height="2.5" rx="1.25" fill="#0B8A5C" />
          </g>
          <g className="li-chip">
            <rect x="214" y="96" width="78" height="32" rx="8" fill={INK} filter={lift} />
            <path className="li-pulse" d="M226 106l1.6 4 4 1.6-4 1.6-1.6 4-1.6-4-4-1.6 4-1.6z" fill={GLOW} />
            <rect className="li-fill" x="238" y="108" width="42" height="4" rx="2" fill="#FFFFFF" opacity=".9" />
            <rect x="238" y="115" width="28" height="3.5" rx="1.75" fill="#FFFFFF" opacity=".45" />
          </g>
        </>
      )
    case "connector":
      return (
        <>
          <path className="li-flow" d="M142 70 H206" stroke="#0B8A5C" strokeWidth="2.4" strokeDasharray="4 4" />
          <g className="li-float">
            <rect x="92" y="44" width="52" height="52" rx="14" fill={INK} filter={lift} />
            <path d="M108 58h26l-3 5h-26z M105 67h26l-3 5h-26z M102 76h22l-3 5h-22z" fill={GLOW} />
          </g>
          <g className="li-chip">
            <rect x="204" y="44" width="52" height="52" rx="14" fill="#FFFFFF" stroke={RULE} filter={lift} />
            <ellipse cx="230" cy="57" rx="13" ry="4.5" fill="#FFFFFF" stroke={accent} strokeWidth="2.4" />
            <path d="M217 57v26c0 2.5 5.8 4.5 13 4.5s13-2 13-4.5V57" fill="none" stroke={accent} strokeWidth="2.4" />
            <path className="li-pulse" d="M217 66c0 2.5 5.8 4.5 13 4.5s13-2 13-4.5" fill="none" stroke={accent} strokeWidth="2.4" />
            <path className="li-pulse" d="M217 75c0 2.5 5.8 4.5 13 4.5s13-2 13-4.5" fill="none" stroke={accent} strokeWidth="2.4" style={{ animationDelay: "-1.2s" }} />
          </g>
          <rect x="160" y="60" width="28" height="20" rx="10" fill="#FFFFFF" stroke={RULE} filter={lift} />
          <circle className="li-ring" cx="174" cy="70" r="4" fill="none" stroke={GLOW} strokeWidth="1.5" />
          <circle cx="174" cy="70" r="4" fill={GLOW} />
          <g filter={lift}>
            <rect x="96" y="108" width="40" height="18" rx="9" fill="#FFFFFF" stroke={RULE} />
            <rect x="142" y="108" width="40" height="18" rx="9" fill="#FFFFFF" stroke={RULE} />
            <rect x="188" y="108" width="40" height="18" rx="9" fill="#FFFFFF" stroke={RULE} />
          </g>
          <rect className="li-pulse" x="104" y="115" width="24" height="4" rx="2" fill={accent} opacity=".7" />
          <rect className="li-pulse" x="150" y="115" width="24" height="4" rx="2" fill={accent} opacity=".7" style={{ animationDelay: "-0.8s" }} />
          <rect className="li-pulse" x="196" y="115" width="24" height="4" rx="2" fill={accent} opacity=".7" style={{ animationDelay: "-1.6s" }} />
        </>
      )
  }
}

/**
 * Listing cover: a crisp product card that previews what the listing produces,
 * on the department's grained paper ground.
 */
export function ListingCover({
  kind,
  department,
  className,
  children,
}: {
  kind: ListingKind
  department: string | null | undefined
  className?: string
  children?: ReactNode
}) {
  const dept = identityDepartmentFor(department)
  const { base, mesh } = dept.cover
  const id = useSvgId("lc")
  return (
    <div className={cn("li-cover", className)} data-kind={kind} data-dept={dept.id}>
      <svg viewBox="12 0 320 150" preserveAspectRatio="xMidYMid slice" width="100%" height="100%" aria-hidden>
        <defs>
          <filter id={`${id}g`} x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="2" stitchTiles="stitch" />
            <feColorMatrix values="0 0 0 0 0.15 0 0 0 0 0.13 0 0 0 0 0.1 0.9 0 0 0 -0.4" />
          </filter>
          <filter id={`${id}s`} x="-20%" y="-20%" width="140%" height="160%">
            <feDropShadow dx="0" dy="3" stdDeviation="4" floodColor="#141513" floodOpacity="0.09" />
          </filter>
          <filter id={`${id}b`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="20" />
          </filter>
          <pattern id={`${id}d`} width="9" height="9" patternUnits="userSpaceOnUse">
            <circle cx="1.5" cy="1.5" r="0.7" fill="#262826" />
          </pattern>
          <linearGradient id={`${id}f`} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0.35" stopColor="#FFFFFF" stopOpacity="0" />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity="1" />
          </linearGradient>
          <mask id={`${id}m`}>
            <rect x="12" width="320" height="150" fill={`url(#${id}f)`} />
          </mask>
        </defs>
        <rect width="340" height="150" fill={base} />
        <g filter={`url(#${id}b)`}>
          <circle className="li-drift" cx="70" cy="10" r="78" fill={mesh[0]} />
          <circle className="li-drift" cx="200" cy="160" r="84" fill={mesh[1]} opacity="0.8" style={{ animationDelay: "-5s" }} />
          <circle className="li-drift" cx="320" cy="4" r="74" fill={mesh[2]} style={{ animationDelay: "-9s" }} />
        </g>
        <rect width="340" height="150" fill={`url(#${id}d)`} opacity="0.2" mask={`url(#${id}m)`} />
        <rect width="340" height="150" filter={`url(#${id}g)`} opacity="0.45" />
        <CoverScene kind={kind} accent={dept.color} shadow={`${id}s`} />
      </svg>
      {children}
    </div>
  )
}

/**
 * Agent detail cover: an atmospheric field, never an illustration that
 * competes with the content. Three drifting color fields, a dot grid fading in
 * from the right and a line-art cluster in a light tint of the department color.
 */
export function DepartmentCover({
  department,
  kindLabel = "Agent",
  roleLabel,
  className,
  children,
}: {
  department: string | null | undefined
  kindLabel?: string
  roleLabel?: string | null
  className?: string
  children?: ReactNode
}) {
  const dept = identityDepartmentFor(department)
  const { base, mesh, stroke, marks, companions } = dept.cover
  const id = useSvgId("dc")
  return (
    <div className={cn("li-banner", className)} data-dept={dept.id}>
      <svg viewBox="0 0 1300 168" preserveAspectRatio="xMaxYMid slice" width="100%" height="100%" aria-hidden>
        <defs>
          <filter id={`${id}g`} x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves="2" stitchTiles="stitch" />
            <feColorMatrix values="0 0 0 0 0.15 0 0 0 0 0.13 0 0 0 0 0.1 0.9 0 0 0 -0.38" />
          </filter>
          <filter id={`${id}b`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="55" />
          </filter>
          <linearGradient id={`${id}f`} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0.35" stopColor="#FFFFFF" stopOpacity="0" />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity="1" />
          </linearGradient>
          <pattern id={`${id}d`} width="16" height="16" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1" fill="#262826" />
          </pattern>
          <mask id={`${id}m`}>
            <rect width="1300" height="168" fill={`url(#${id}f)`} />
          </mask>
        </defs>
        <rect width="1300" height="168" fill={base} />
        <g filter={`url(#${id}b)`}>
          <circle className="li-drift-wide" cx="260" cy="20" r="210" fill={mesh[0]} />
          <circle className="li-drift-far" cx="820" cy="190" r="220" fill={mesh[1]} opacity="0.8" />
          <circle className="li-drift-wide" cx="1180" cy="10" r="200" fill={mesh[2]} style={{ animationDuration: "22s" }} />
        </g>
        <rect width="1300" height="168" fill={`url(#${id}d)`} opacity="0.2" mask={`url(#${id}m)`} />
        <g className="li-parallax" fill="none" stroke={stroke} strokeLinecap="round" strokeLinejoin="round">
          {companions
            ? companions.map((mark, index) => (
                <g key={`c${index}`} transform={`translate(${mark.x} ${mark.y}) scale(${mark.scale})`} opacity={mark.opacity}>
                  <path d={mark.d} strokeWidth={mark.width} vectorEffect="non-scaling-stroke" />
                </g>
              ))
            : COVER_RINGS.map((ring) => <circle key={ring.cx} cx={ring.cx} cy={ring.cy} r={ring.r} strokeWidth="4" opacity="0.8" />)}
          {marks.map((mark, index) => (
            <g key={index} transform={`translate(${mark.x} ${mark.y}) scale(${mark.scale})`} opacity={mark.opacity}>
              <path d={mark.d} strokeWidth={mark.width} vectorEffect="non-scaling-stroke" />
            </g>
          ))}
        </g>
        <rect width="1300" height="168" filter={`url(#${id}g)`} opacity="0.45" />
      </svg>
      <div className="li-banner-tags">
        <span className="li-tag light">{kindLabel}</span>
        <span className="li-tag dark">{dept.label}</span>
        {roleLabel ? <span className="li-tag plain">{roleLabel}</span> : null}
      </div>
      {children}
    </div>
  )
}
