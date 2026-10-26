"use client"

import { createContext, useContext, type ReactNode } from "react"
import { AccessArt, ApprovalsArt, ArtFrame } from "@/components/agents/art/agents-art"
import { AuditArt, SecurityArt } from "@/components/dashboard/art/dashboard-art"

/**
 * Hero scenes for the Trust & Safety tabs (TrustSafety-Art design). Every scene
 * sits in the shared art frame (colour wash, dot field, ground line and grain)
 * and is drawn from live state where the tab has one, so the picture never
 * claims something the page does not: the decision monitor shows a waiting card
 * only when a request waits, each policy switch is on only when its rule is on,
 * and a stage's server lights up only once it is set up.
 */

export type TrustSafetyArtKind = "approvals" | "audit" | "policies" | "security" | "roles" | "envs" | "access"

export type TrustSafetyArtState = {
  /** Approvals: requests waiting for a decision. */
  waiting?: number
  /** Policies: one flag per org approval rule, in the order the tab lists them. */
  rules?: boolean[]
  /** Environments: whether Development, Staging and Production are set up. */
  stages?: [boolean, boolean, boolean]
}

const SWITCH_ROWS = [84, 112, 140, 168]

/** Policies: a control panel of rule switches beside a checkpoint gate holding an agent until it is cleared. */
export function PoliciesArt({ rules }: { rules?: boolean[] }) {
  const flags = SWITCH_ROWS.map((_, i) => (rules ? Boolean(rules[i]) : i !== 2))
  const on = flags.filter(Boolean).length
  return (
    <ArtFrame
      label={`A control panel with ${on} of ${flags.length} policy switches on beside a checkpoint gate holding an agent until it is cleared`}
      wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#DCE6DC" }}
      ground={[28, 292]}
    >
      <rect x="52" y="48" width="118" height="150" rx="12" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="3" />
      <rect x="54" y="50" width="114" height="24" rx="10" fill="#E9E2D3" />
      <circle cx="68" cy="61" r="4" fill="#B5654A" />
      <circle cx="80" cy="61" r="4" fill="#C9A24B" />
      <circle cx="92" cy="61" r="4" fill="#2E9E5B" />
      {SWITCH_ROWS.map((y, i) => (
        <g key={y}>
          <rect x="66" y={y + 5} width={[52, 44, 48, 40][i]} height="6" rx="3" fill="#CFC6B6" />
          <rect x="126" y={y} width="30" height="16" rx="8" fill={flags[i] ? "#2E9E5B" : "#C9C2B2"} className={flags[i] ? undefined : "g-pulse"} />
          <circle cx={flags[i] ? 148 : 134} cy={y + 8} r="6" fill="#F7F4EC" />
        </g>
      ))}
      <path d="M176 204 H292" stroke="#9C8C74" strokeWidth="2" strokeDasharray="4 7" className="g-flow" />
      <rect x="226" y="112" width="10" height="102" rx="3" fill="#6B5B47" />
      <circle cx="231" cy="108" r="7" fill="#B5654A" className="g-pulse" />
      <rect x="231" y="128" width="64" height="10" rx="3" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="2" />
      <rect x="243" y="129" width="9" height="8" fill="#B5654A" />
      <rect x="263" y="129" width="9" height="8" fill="#B5654A" />
      <rect x="283" y="129" width="9" height="8" fill="#B5654A" />
      <g className="g-nudge">
        <rect x="184" y="166" width="34" height="30" rx="7" fill="#3B4250" />
        <rect x="198" y="158" width="6" height="8" rx="2" fill="#3B4250" />
        <circle cx="194" cy="179" r="3" fill="#4CC27F" className="g-twinkle" />
        <circle cx="208" cy="179" r="3" fill="#4CC27F" className="g-twinkle" style={{ animationDelay: "-0.6s" }} />
        <rect x="187" y="196" width="8" height="10" rx="2" fill="#26282C" />
        <rect x="207" y="196" width="8" height="10" rx="2" fill="#26282C" />
      </g>
      <g className="g-float" style={{ animationDelay: "-1.2s" }}>
        <circle cx="262" cy="72" r="18" fill="#FBF8F1" stroke="#CFC6B6" />
        <rect x="255" y="64" width="5" height="16" rx="1.5" fill="#C9A24B" />
        <rect x="264" y="64" width="5" height="16" rx="1.5" fill="#C9A24B" />
      </g>
      <g className="g-beat" style={{ transformOrigin: "196px 120px" }}>
        <circle cx="196" cy="120" r="13" fill="#2E9E5B" />
        <path d="M190 120 l4 4 l8 -9" stroke="#FFFFFF" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </ArtFrame>
  )
}

/** Role permissions: three access badges on lanyards, each with a different number of permission bars. */
export function RolesArt() {
  return (
    <ArtFrame
      label="Three access badges on lanyards, each with a different symbol and a different number of permission bars"
      wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#E3E6DA" }}
      ground={[28, 292]}
    >
      <path d="M70 14 L82 70 M98 14 L86 70" stroke="#2E9E5B" strokeWidth="4" strokeLinecap="round" />
      <path d="M148 6 L156 58 M172 6 L164 58" stroke="#4A6A8E" strokeWidth="4" strokeLinecap="round" />
      <path d="M224 14 L234 74 M252 14 L240 74" stroke="#C9A24B" strokeWidth="4" strokeLinecap="round" />
      <g className="g-bob" style={{ animationDelay: "-0.6s" }}>
        <g transform="rotate(-8 84 122)">
          <rect x="50" y="70" width="68" height="100" rx="10" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="3" />
          <rect x="74" y="64" width="20" height="12" rx="3" fill="#6B5B47" />
          <circle cx="84" cy="106" r="17" fill="#2E9E5B" />
          <path d="M74 112 l3 -11 7 6 7 -6 3 11 z" fill="#F7F4EC" />
          <rect x="62" y="134" width="44" height="6" rx="3" fill="#2E9E5B" />
          <rect x="62" y="144" width="44" height="6" rx="3" fill="#2E9E5B" />
          <rect x="62" y="154" width="44" height="6" rx="3" fill="#2E9E5B" />
        </g>
      </g>
      <g className="g-bob">
        <rect x="124" y="58" width="72" height="108" rx="10" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="3" />
        <rect x="150" y="52" width="20" height="12" rx="3" fill="#6B5B47" />
        <circle cx="160" cy="96" r="18" fill="#4A6A8E" />
        <path d="M152 96 h16 M160 88 v16" stroke="#F7F4EC" strokeWidth="3.5" strokeLinecap="round" />
        <rect x="136" y="126" width="48" height="6" rx="3" fill="#2E9E5B" />
        <rect x="136" y="136" width="48" height="6" rx="3" fill="#2E9E5B" />
        <rect x="136" y="146" width="48" height="6" rx="3" fill="#CFC6B6" />
      </g>
      <g className="g-bob" style={{ animationDelay: "-1.2s" }}>
        <g transform="rotate(8 238 126)">
          <rect x="204" y="74" width="68" height="100" rx="10" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="3" />
          <rect x="228" y="68" width="20" height="12" rx="3" fill="#6B5B47" />
          <circle cx="238" cy="110" r="17" fill="#C9A24B" />
          <ellipse cx="238" cy="110" rx="10" ry="6" fill="#F7F4EC" />
          <circle cx="238" cy="110" r="3.4" fill="#26282C" />
          <rect x="216" y="138" width="44" height="6" rx="3" fill="#2E9E5B" />
          <rect x="216" y="148" width="44" height="6" rx="3" fill="#CFC6B6" />
          <rect x="216" y="158" width="44" height="6" rx="3" fill="#CFC6B6" />
        </g>
      </g>
    </ArtFrame>
  )
}

function Server({ x, live }: { x: number; live: boolean }) {
  return (
    <>
      <g opacity={live ? undefined : 0.85}>
        <rect x={x} y="118" width="68" height="84" rx="8" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="3" strokeDasharray={live ? undefined : "6 4"} />
        {[130, 150, 170].map((y, i) => (
          <g key={y}>
            <rect x={x + 10} y={y} width="48" height="14" rx="3" fill={live ? "#3B4250" : "#E9E2D3"} />
            <circle
              cx={x + 50}
              cy={y + 7}
              r="3"
              fill={live ? "#4CC27F" : "#C9C2B2"}
              className={live ? "g-twinkle" : undefined}
              style={live ? { animationDelay: `${-0.8 * i}s` } : undefined}
            />
          </g>
        ))}
      </g>
      <rect x={x + 14} y="202" width="12" height="12" fill={live ? "#6B5B47" : "#9C8C74"} />
      <rect x={x + 42} y="202" width="12" height="12" fill={live ? "#6B5B47" : "#9C8C74"} />
    </>
  )
}

/** Environments: Development, Staging and Production in a row; a package travels toward the live server. */
export function EnvironmentsArt({ stages }: { stages?: [boolean, boolean, boolean] }) {
  const live = stages ?? [false, false, true]
  const ready = live.filter(Boolean).length
  return (
    <ArtFrame
      label={`Three servers in a row linked by a dashed path, ${ready} of 3 set up, a package travelling toward the live server marked with a green flag`}
      wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#DCE4E6" }}
    >
      <path d="M104 160 H124 M194 160 H214" stroke="#9C8C74" strokeWidth="2.5" strokeDasharray="4 6" className="g-flow" />
      <path d="M118 155 l6 5 -6 5 M208 155 l6 5 -6 5" stroke="#9C8C74" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <Server x={36} live={live[0]} />
      <Server x={126} live={live[1]} />
      <Server x={216} live={live[2]} />
      <path d="M250 118 V66" stroke="#6B5B47" strokeWidth="3" strokeLinecap="round" />
      <path d="M250 66 h26 l-7 8 7 8 h-26 z" fill="#2E9E5B" className="g-pulse" />
      <path d="M44 92 H276" stroke="#CFC6B6" strokeWidth="2" strokeDasharray="2 6" />
      <g className="g-run">
        <rect x="20" y="84" width="18" height="16" rx="3" fill="#C9A24B" stroke="#6B5B47" strokeWidth="2" />
        <path d="M20 90 h18 M29 84 v6" stroke="#6B5B47" strokeWidth="1.6" />
      </g>
    </ArtFrame>
  )
}

/** Lets a host (the Settings pages) swap a tab's scene for its own art. */
export const TrustSafetyArtOverrides = createContext<Partial<Record<TrustSafetyArtKind, ReactNode>>>({})

function scene(kind: TrustSafetyArtKind, state: TrustSafetyArtState): ReactNode {
  switch (kind) {
    case "approvals":
      return <ApprovalsArt waiting={state.waiting ?? 0} />
    case "audit":
      return <AuditArt label="A clipboard ledger with a timeline of green events and one red event under a magnifying glass" />
    case "policies":
      return <PoliciesArt rules={state.rules} />
    case "security":
      return <SecurityArt label="A shield with a green padlock inside a dashed ring, surrounded by a sign in code, a globe and a clock" />
    case "roles":
      return <RolesArt />
    case "envs":
      return <EnvironmentsArt stages={state.stages} />
    case "access":
      return <AccessArt />
  }
}

export function TrustSafetyArt({ kind, state = {} }: { kind: TrustSafetyArtKind; state?: TrustSafetyArtState }) {
  const override = useContext(TrustSafetyArtOverrides)[kind]
  return <div className="ts-art ts-artbox">{override ?? scene(kind, state)}</div>
}
