"use client"

import { useId, type ReactNode } from "react"
import { ArtFrame } from "@/components/agents/art/agents-art"
import "./dashboard-art.css"

/**
 * Hero scenes from the Dashboard designs. They share the Agents art frame (colour wash,
 * dot field, ground line and grain), so the motion classes and reduced-motion rules in
 * agents-art.css apply here too.
 */

const LABEL_DashboardTeamArt = "A team of four gathered around a table, agreeing on one recommendation"
const LABEL_WorkflowsArt = "A person guiding work through a workflow pipeline to a green finish"
const LABEL_PlaysArt = "A person moving a piece on a strategy board where three lanes meet at a target"
const LABEL_PlayDetailArt = "Two people shaking hands next to a growth chart"
const LABEL_SchedulesArt = "A wall calendar with some failed days marked red beside a ticking clock"
const LABEL_AuditArt = "A clipboard ledger with a timeline of green events and one red event under a magnifying glass"
const LABEL_ApiKeysArt = "A brass key heading toward a plug that connects to a terminal window with lines of code"
const LABEL_BillingArt = "A person checking a tablet beside a paid receipt with a green check stamp and a usage meter"
const LABEL_OrganizationsArt = "Three office buildings linked by a path, the middle one marked as current, beside an outlined plot for a new one"
const LABEL_SecurityArt = "A shield with a green padlock inside a dashed ring, surrounded by a sign in code, a globe and a clock"
const LABEL_TeamInviteArt = "Two teammates sending an invite envelope along a path to a new teammate waving from an open doorway"

/** Dashboard: four teammates around a table agreeing on one recommendation. */
export function DashboardTeamArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_DashboardTeamArt} wash={{ cx: 160, cy: 128, rx: 145, ry: 110, fill: "#CFE0D5" }} ground={[28, 292]}>
      <g stroke="#5E6B62" strokeWidth="1.5" strokeDasharray="3 4" fill="none" className="g-flow">
        <path d="M126 98 L150 76" />
        <path d="M194 98 L170 76" />
        <path d="M66 94 Q90 60 138 58" />
        <path d="M254 94 Q230 60 182 58" />
      </g>
      <g className="g-float">
        <rect x="132" y="34" width="56" height="42" rx="9" fill="#F5F2EA" />
        <circle cx="160" cy="55" r="11" fill="#2E9E5B" />
        <path d="M154 55 l4 4 l8 -9" fill="none" stroke="#F5F2EA" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <path className="g-twinkle" d="M200 30 l2.5 6 l6 2.5 l-6 2.5 l-2.5 6 l-2.5 -6 l-6 -2.5 l6 -2.5 Z" fill="#C9A24B" />
      <g transform="translate(126 0)">
        <path d="M-14 128 Q0 120 14 128 L16 174 L-16 174 Z" fill="#5B5BD6" />
        <path d="M-12 132 L-16 156 L-8 164" fill="none" stroke="#5B5BD6" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="0" cy="110" r="10" fill="#C99572" />
        <path d="M-10.5 109 A10.5 10.5 0 0 1 10.5 109 Q0 101 -10.5 109 Z" fill="#1F1A17" />
      </g>
      <g transform="translate(194 0)">
        <path d="M-14 128 Q0 120 14 128 L16 174 L-16 174 Z" fill="#B0573F" />
        <path d="M12 132 L16 156 L8 164" fill="none" stroke="#B0573F" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="0" cy="110" r="10" fill="#D6AB86" />
        <path d="M-10.5 109 A10.5 10.5 0 0 1 10.5 109 Q0 101 -10.5 109 Z" fill="#2E231D" />
        <circle cx="0" cy="98" r="4.5" fill="#2E231D" />
      </g>
      <rect x="154" y="178" width="12" height="36" fill="#6E5A44" />
      <ellipse cx="160" cy="213" rx="26" ry="4" fill="#6E5A44" />
      <ellipse cx="160" cy="174" rx="80" ry="14" fill="#8A6A4E" />
      <ellipse cx="160" cy="171" rx="80" ry="13" fill="#A07E60" />
      <rect x="124" y="165" width="20" height="7" rx="1" fill="#F5F2EA" />
      <rect x="176" y="160" width="26" height="10" rx="2" fill="#3B4250" />
      <g transform="translate(66 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <path d="M-13 124 Q0 116 13 124 L15 168 L-15 168 Z" fill="#7C8F6B" />
        <path d="M-10 128 L-12 160" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" />
        <circle cx="-12" cy="162" r="3.2" fill="#D6AB86" />
        <path d="M9 128 L20 144 L30 146" fill="none" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="32" cy="146" r="3.2" fill="#D6AB86" />
        <circle cx="0" cy="106" r="10" fill="#D6AB86" />
        <path d="M-10.5 105 A10.5 10.5 0 0 1 10.5 105 Q2 97 -10.5 105 Z" fill="#2E231D" />
        <circle cx="-8" cy="97" r="4.5" fill="#2E231D" />
      </g>
      <g transform="translate(254 0) scale(-1 1)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <path d="M-13 124 Q0 116 13 124 L15 168 L-15 168 Z" fill="#C9A24B" />
        <path d="M-10 128 L-12 160" stroke="#C9A24B" strokeWidth="6" strokeLinecap="round" />
        <circle cx="-12" cy="162" r="3.2" fill="#C99572" />
        <path d="M9 127 L22 116 L30 104" fill="none" stroke="#C9A24B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="31" cy="102" r="3.2" fill="#C99572" />
        <circle cx="0" cy="106" r="10" fill="#C99572" />
        <path d="M-10.5 106 A10.5 10.5 0 0 1 10.5 106 L10 102 Q0 96 -10.5 106 Z" fill="#1F1A17" />
      </g>
    </ArtFrame>
  )
}

/** Workflows: a person guiding cards along a pipeline to a green finish. */
export function WorkflowsArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_WorkflowsArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#CFE0D2" }} ground={[28, 292]}>
      <path d="M40 82 H262" stroke="#7C8F6B" strokeWidth="2.5" strokeDasharray="6 6" className="g-flow" />
      <path d="M128 100 V128 H208 V100" stroke="#A9B79A" strokeWidth="2" strokeDasharray="4 5" fill="none" className="g-flow" />
      <g className="g-float" style={{ animationDelay: "0s" }}>
        <rect x="38" y="64" width="44" height="36" rx="6" fill="#FBF8F1" />
        <rect x="44" y="72" width="10" height="10" rx="2" fill="#D9824B" />
        <rect x="58" y="74" width="20" height="3" rx="1.5" fill="#CFC6B6" />
        <rect x="44" y="86" width="30" height="3" rx="1.5" fill="#E2DACB" />
      </g>
      <g className="g-float" style={{ animationDelay: "-1.2s" }}>
        <rect x="106" y="64" width="44" height="36" rx="6" fill="#FBF8F1" />
        <rect x="112" y="72" width="10" height="10" rx="2" fill="#4A6A8E" />
        <rect x="126" y="74" width="20" height="3" rx="1.5" fill="#CFC6B6" />
        <rect x="112" y="86" width="30" height="3" rx="1.5" fill="#E2DACB" />
      </g>
      <g className="g-float" style={{ animationDelay: "-2.4s" }}>
        <rect x="174" y="64" width="44" height="36" rx="6" fill="#FBF8F1" />
        <rect x="180" y="72" width="10" height="10" rx="2" fill="#C9A24B" />
        <rect x="194" y="74" width="20" height="3" rx="1.5" fill="#CFC6B6" />
        <rect x="180" y="86" width="30" height="3" rx="1.5" fill="#E2DACB" />
      </g>
      <circle cx="262" cy="82" r="17" fill="#2E9E5B" className="g-pulse" />
      <path d="M254 82 l6 6 l11 -12" stroke="#FFFFFF" strokeWidth="3.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <g transform="translate(-8 0)">
        <circle cx="40" cy="82" r="5" fill="#2E9E5B" className="g-run" />
      </g>
      <rect x="186" y="132" width="44" height="30" rx="5" fill="#FBF8F1" />
      <rect x="194" y="140" width="22" height="3" rx="1.5" fill="#CFC6B6" />
      <rect x="194" y="149" width="28" height="3" rx="1.5" fill="#E2DACB" />
      <g transform="translate(96 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(-6 -4 164)" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(8 4 164)" />
        <path d="M-12 124 Q1 116 14 124 L16 168 L-14 168 Z" fill="#4A6A8E" />
        <path d="M-8 129 L10 112 L26 100" fill="none" stroke="#4A6A8E" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="28" cy="99" r="3.2" fill="#D6AB86" />
        <path d="M10 128 L18 146 L12 160" fill="none" stroke="#4A6A8E" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="12" cy="161" r="3.2" fill="#D6AB86" />
        <circle cx="1" cy="106" r="10" fill="#D6AB86" />
        <path d="M-9.5 105 A10.5 10.5 0 0 1 11.5 105 Q3 97 -9.5 105 Z" fill="#2E231D" />
        <circle cx="-7" cy="97" r="4.5" fill="#2E231D" />
      </g>
      <rect x="269" y="196" width="18" height="18" rx="2" fill="#B5654A" />
      <path d="M278 196 C 276 180 270 172 266 166" stroke="#5E7A5C" strokeWidth="2" fill="none" />
      <path d="M266 166 C 256 160 264 176 274 180 Z" fill="#7C8F6B" className="g-bob" />
      <path d="M278 196 C 282 182 292 174 294 170 Z" fill="#5E7A5C" />
    </ArtFrame>
  )
}

/** Plays: a strategy board where three lanes meet at a target. */
export function PlaysArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_PlaysArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#E8D9BF" }} ground={[28, 292]}>
      <line x1="138" y1="150" x2="126" y2="214" stroke="#6B5B47" strokeWidth="3" />
      <line x1="270" y1="150" x2="282" y2="214" stroke="#6B5B47" strokeWidth="3" />
      <rect x="122" y="44" width="164" height="110" rx="6" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="4" />
      <circle cx="144" cy="68" r="6" fill="#4A6A8E" />
      <path d="M152 68 C 196 68 210 99 236 99" stroke="#4A6A8E" strokeWidth="2.5" fill="none" strokeLinecap="round" className="g-draw" />
      <circle cx="144" cy="99" r="6" fill="#C9A24B" />
      <path d="M152 99 C 196 99 210 99 236 99" stroke="#C9A24B" strokeWidth="2.5" fill="none" strokeLinecap="round" className="g-draw" />
      <circle cx="144" cy="130" r="6" fill="#7C8F6B" />
      <path d="M152 130 C 196 130 210 99 236 99" stroke="#7C8F6B" strokeWidth="2.5" fill="none" strokeLinecap="round" className="g-draw" />
      <circle cx="252" cy="99" r="18" fill="#F2E3D9" stroke="#B5654A" strokeWidth="3" className="g-beat" />
      <circle cx="252" cy="99" r="10" fill="none" stroke="#B5654A" strokeWidth="3" />
      <circle cx="252" cy="99" r="3.5" fill="#B5654A" />
      <rect x="168" y="118" width="28" height="16" rx="8" fill="#F3E2C2" />
      <rect x="174" y="124" width="16" height="3" rx="1.5" fill="#B07A1F" />
      <path d="M268 56 l2.6 6.4 6.4 2.6 -6.4 2.6 -2.6 6.4 -2.6 -6.4 -6.4 -2.6 6.4 -2.6z" fill="#C9A24B" className="g-twinkle" />
      <g transform="translate(86 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(-6 -4 164)" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(8 4 164)" />
        <path d="M-12 124 Q1 116 14 124 L16 168 L-14 168 Z" fill="#B5654A" />
        <path d="M-8 129 L-4 150 L-6 164" fill="none" stroke="#B5654A" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-6" cy="165" r="3.2" fill="#B98563" />
        <path d="M10 128 L26 116 L40 112" fill="none" stroke="#B5654A" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="42" cy="111" r="3.2" fill="#B98563" />
        <circle cx="1" cy="106" r="10" fill="#B98563" />
        <path d="M-9.5 105 A10.5 10.5 0 0 1 11.5 105 Q3 97 -9.5 105 Z" fill="#3A2A20" />
      </g>
      <g className="g-nudge">
        <circle cx="138" cy="96" r="5.5" fill="#26282C" />
        <path d="M133 108 h10 l-2 -8 h-6 z" fill="#26282C" />
      </g>
      <rect x="39" y="196" width="18" height="18" rx="2" fill="#B5654A" />
      <path d="M48 196 C 46 180 40 172 36 166" stroke="#5E7A5C" strokeWidth="2" fill="none" />
      <path d="M36 166 C 26 160 34 176 44 180 Z" fill="#7C8F6B" className="g-bob" />
      <path d="M48 196 C 52 182 62 174 64 170 Z" fill="#5E7A5C" />
    </ArtFrame>
  )
}

/** Play detail: two people shaking hands beside a growth chart. */
export function PlayDetailArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_PlayDetailArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#CACCE8" }} ground={[28, 292]}>
      <rect x="200" y="172" width="18" height="42" rx="2" fill="#5B5BD6" opacity="0.5" className="g-grow" />
      <rect x="224" y="148" width="18" height="66" rx="2" fill="#5B5BD6" opacity="0.72" className="g-grow" style={{ animationDelay: "0.5s" }} />
      <rect x="248" y="120" width="18" height="94" rx="2" fill="#5B5BD6" className="g-grow" style={{ animationDelay: "1s" }} />
      <polyline className="g-draw" points="196,158 220,136 236,146 266,104" fill="none" stroke="#26282C" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      <polygon points="271,97 256,101 266,112" fill="#26282C" />
      <g transform="translate(112 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <path d="M-13 124 Q0 116 13 124 L15 168 L-15 168 Z" fill="#7C8F6B" />
        <path d="M-10 128 L-13 160" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" />
        <circle cx="-13" cy="162" r="3.2" fill="#D6AB86" />
        <path d="M9 128 L18 142 L26 146" fill="none" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="0" cy="106" r="10" fill="#D6AB86" />
        <path d="M-10.5 105 A10.5 10.5 0 0 1 10.5 105 Q2 97 -10.5 105 Z" fill="#2E231D" />
        <circle cx="-8" cy="97" r="4.5" fill="#2E231D" />
      </g>
      <g transform="translate(164 0) scale(-1 1)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" />
        <path d="M-13 124 Q0 116 13 124 L15 168 L-15 168 Z" fill="#B0573F" />
        <path d="M-10 128 L-12 160" stroke="#B0573F" strokeWidth="6" strokeLinecap="round" />
        <circle cx="-12" cy="162" r="3.2" fill="#C99572" />
        <path d="M9 128 L18 142 L26 146" fill="none" stroke="#B0573F" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="0" cy="106" r="10" fill="#C99572" />
        <path d="M-10.5 106 A10.5 10.5 0 0 1 10.5 106 L10 102 Q0 96 -10.5 106 Z" fill="#1F1A17" />
      </g>
      <circle cx="138" cy="146" r="4" fill="#D6AB86" />
    </ArtFrame>
  )
}

/** Schedules: a wall calendar with failed days marked red beside a ticking clock. */
export function SchedulesArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_SchedulesArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#CFD3E6" }} ground={[28, 292]}>
      <rect x="36" y="44" width="156" height="132" rx="6" fill="#F7F4EC" />
      <rect x="36" y="44" width="156" height="22" rx="6" fill="#4A6A8E" />
      <rect x="36" y="58" width="156" height="8" fill="#4A6A8E" />
      <rect x="62" y="36" width="5" height="16" rx="2.5" fill="#26282C" />
      <rect x="160" y="36" width="5" height="16" rx="2.5" fill="#26282C" />
      <rect x="46" y="74" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="75" y="74" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="104" y="74" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="116" cy="84" r="4.5" fill="#2E9E5B" />
      <rect x="133" y="74" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="162" y="74" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="174" cy="84" r="4.5" fill="#2E9E5B" />
      <rect x="46" y="98" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="75" y="98" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="87" cy="108" r="4.5" fill="#2E9E5B" />
      <rect x="104" y="98" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="133" y="98" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="145" cy="108" r="4.5" fill="#A3333D" className="g-pulse" />
      <rect x="162" y="98" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="174" cy="108" r="4.5" fill="#2E9E5B" />
      <rect x="46" y="122" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="75" y="122" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="75" y="122" width="25" height="20" rx="3" fill="none" stroke="#26282C" strokeWidth="2" />
      <rect x="104" y="122" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="133" y="122" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="145" cy="132" r="4.5" fill="#A3333D" className="g-pulse" />
      <rect x="162" y="122" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="46" y="146" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="58" cy="156" r="4.5" fill="#2E9E5B" />
      <rect x="75" y="146" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="104" y="146" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="116" cy="156" r="4.5" fill="#2E9E5B" />
      <rect x="133" y="146" width="25" height="20" rx="3" fill="#E6E1D6" />
      <rect x="162" y="146" width="25" height="20" rx="3" fill="#E6E1D6" />
      <circle cx="246" cy="72" r="28" fill="#F7F4EC" stroke="#26282C" strokeWidth="3" />
      <line x1="246.0" y1="50.0" x2="246.0" y2="47.0" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="257.0" y1="52.9" x2="258.5" y2="50.3" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="265.1" y1="61.0" x2="267.7" y2="59.5" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="268.0" y1="72.0" x2="271.0" y2="72.0" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="265.1" y1="83.0" x2="267.7" y2="84.5" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="257.0" y1="91.1" x2="258.5" y2="93.7" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="246.0" y1="94.0" x2="246.0" y2="97.0" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="235.0" y1="91.1" x2="233.5" y2="93.7" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="226.9" y1="83.0" x2="224.3" y2="84.5" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="224.0" y1="72.0" x2="221.0" y2="72.0" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="226.9" y1="61.0" x2="224.3" y2="59.5" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="235.0" y1="52.9" x2="233.5" y2="50.3" stroke="#9C8C74" strokeWidth="1.6" />
      <line x1="246" y1="72" x2="257" y2="77" stroke="#26282C" strokeWidth="3" strokeLinecap="round" />
      <g className="g-spin">
        <circle cx="246" cy="72" r="19" fill="none" />
        <line x1="246" y1="72" x2="246" y2="54" stroke="#B5654A" strokeWidth="2.4" strokeLinecap="round" />
      </g>
      <circle cx="246" cy="72" r="3" fill="#26282C" />
      <g transform="translate(244 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(-6 -4 164)" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(8 4 164)" />
        <path d="M-12 124 Q1 116 14 124 L16 168 L-14 168 Z" fill="#7C8F6B" />
        <path d="M-8 129 L-16 142 L-24 146" fill="none" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-26" cy="146" r="3.2" fill="#D6AB86" />
        <path d="M10 128 L2 142 L-18 148" fill="none" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-20" cy="148" r="3.2" fill="#D6AB86" />
        <circle cx="1" cy="106" r="10" fill="#D6AB86" />
        <path d="M-9.5 105 A10.5 10.5 0 0 1 11.5 105 Q3 97 -9.5 105 Z" fill="#2E231D" />
        <circle cx="-7" cy="97" r="4.5" fill="#2E231D" />
      </g>
      <rect x="212" y="134" width="20" height="26" rx="3" fill="#26282C" transform="rotate(-8 222 147)" />
      <rect x="215" y="138" width="14" height="16" rx="2" fill="#9FD3B4" transform="rotate(-8 222 147)" />
      <rect x="58" y="190" width="40" height="24" rx="3" fill="#B98D63" />
      <rect x="64" y="196" width="28" height="3" rx="1.5" fill="#9C734D" />
    </ArtFrame>
  )
}

/** Audit trail: a clipboard ledger of events under a magnifying glass. */
export function AuditArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_AuditArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#E2E6D2" }} ground={[28, 292]}>
      <rect x="98" y="44" width="124" height="160" rx="8" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="3" />
      <rect x="134" y="36" width="52" height="16" rx="5" fill="#6B5B47" />
      <line x1="120" y1="72" x2="120" y2="186" stroke="#CFC6B6" strokeWidth="2" />
      <circle cx="120" cy="74" r="6" fill="#2E9E5B" />
      <rect x="134" y="68" width="54" height="5" rx="2.5" fill="#B5A58C" />
      <rect x="134" y="77" width="72" height="4" rx="2" fill="#E2DACB" />
      <circle cx="120" cy="101" r="6" fill="#2E9E5B" />
      <rect x="134" y="95" width="50" height="5" rx="2.5" fill="#B5A58C" />
      <rect x="134" y="104" width="66" height="4" rx="2" fill="#E2DACB" />
      <circle cx="120" cy="128" r="6" fill="#A3333D" className="g-pulse" />
      <rect x="134" y="122" width="46" height="5" rx="2.5" fill="#B5A58C" />
      <rect x="134" y="131" width="60" height="4" rx="2" fill="#E2DACB" />
      <circle cx="120" cy="155" r="6" fill="#2E9E5B" />
      <rect x="134" y="149" width="42" height="5" rx="2.5" fill="#B5A58C" />
      <rect x="134" y="158" width="54" height="4" rx="2" fill="#E2DACB" />
      <circle cx="120" cy="182" r="6" fill="#2E9E5B" />
      <rect x="134" y="176" width="38" height="5" rx="2.5" fill="#B5A58C" />
      <rect x="134" y="185" width="48" height="4" rx="2" fill="#E2DACB" />
      <g className="g-nudge">
        <circle cx="214" cy="146" r="24" fill="#FBF8F1" fillOpacity=".55" stroke="#26282C" strokeWidth="5" />
        <line x1="231" y1="163" x2="252" y2="184" stroke="#26282C" strokeWidth="8" strokeLinecap="round" />
      </g>
      <g className="g-float">
        <rect x="236" y="62" width="44" height="54" rx="4" fill="#FBF8F1" stroke="#CFC6B6" />
        <path d="M246 76 h24 M246 86 h18 M246 96 h22" stroke="#CFC6B6" strokeWidth="3" strokeLinecap="round" />
        <rect x="244" y="104" width="14" height="6" rx="2" fill="#4A6A8E" />
      </g>
      <g className="g-float" style={{ animationDelay: "-1.3s" }}>
        <rect x="40" y="86" width="40" height="50" rx="4" fill="#FBF8F1" stroke="#CFC6B6" />
        <path d="M48 98 h22 M48 108 h16 M48 118 h20" stroke="#CFC6B6" strokeWidth="3" strokeLinecap="round" />
      </g>
      <rect x="47" y="196" width="18" height="18" rx="2" fill="#B5654A" />
      <path d="M56 196 C 54 180 48 172 44 166" stroke="#5E7A5C" strokeWidth="2" fill="none" />
      <path d="M44 166 C 34 160 42 176 52 180 Z" fill="#7C8F6B" className="g-bob" />
      <path d="M56 196 C 60 182 70 174 72 170 Z" fill="#5E7A5C" />
    </ArtFrame>
  )
}

/** API keys: a brass key heading for a plug wired to a terminal. */
export function ApiKeysArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_ApiKeysArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#E8DCE4" }} ground={[28, 292]}>
      <rect x="150" y="56" width="128" height="104" rx="8" fill="#26282C" />
      <rect x="150" y="56" width="128" height="18" rx="8" fill="#3A3D42" />
      <rect x="150" y="66" width="128" height="8" fill="#3A3D42" />
      <circle cx="162" cy="65" r="3" fill="#B5654A" />
      <circle cx="172" cy="65" r="3" fill="#C9A24B" />
      <circle cx="182" cy="65" r="3" fill="#7C8F6B" />
      <path d="M164 88 h70" stroke="#9FD3B4" strokeWidth="4" strokeLinecap="round" strokeDasharray="120" className="g-draw" style={{ animationDelay: "0s" }} />
      <path d="M164 103 h52" stroke="#CFC6B6" strokeWidth="4" strokeLinecap="round" strokeDasharray="120" className="g-draw" style={{ animationDelay: "0.3s" }} />
      <path d="M164 118 h84" stroke="#CFC6B6" strokeWidth="4" strokeLinecap="round" strokeDasharray="120" className="g-draw" style={{ animationDelay: "0.6s" }} />
      <path d="M164 133 h40" stroke="#9FD3B4" strokeWidth="4" strokeLinecap="round" strokeDasharray="120" className="g-draw" style={{ animationDelay: "0.9s" }} />
      <rect x="166" y="146" width="8" height="4" fill="#9FD3B4" className="g-pulse" />
      <rect x="132" y="170" width="44" height="30" rx="6" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="2.5" />
      <rect x="146" y="180" width="16" height="10" rx="2" fill="#6B5B47" />
      <path d="M154 170 V160" stroke="#6B5B47" strokeWidth="2.5" />
      <g className="g-nudge">
        <circle cx="72" cy="186" r="20" fill="#C9A24B" />
        <circle cx="72" cy="186" r="8" fill="#E8DCE4" />
        <rect x="90" y="182" width="44" height="8" rx="3" fill="#C9A24B" />
        <rect x="112" y="190" width="6" height="8" rx="1.5" fill="#C9A24B" />
        <rect x="122" y="190" width="6" height="11" rx="1.5" fill="#C9A24B" />
      </g>
      <path d="M60 70 l2.6 6.4 6.4 2.6 -6.4 2.6 -2.6 6.4 -2.6 -6.4 -6.4 -2.6 6.4 -2.6z" fill="#C9A24B" className="g-twinkle" />
      <g className="g-float">
        <rect x="56" y="104" width="62" height="24" rx="12" fill="#FBF8F1" stroke="#CFC6B6" />
        <text x="87" y="120" textAnchor="middle" fontSize="11" fontFamily="Geist Mono, monospace" fill="#55564F">{"{ }"}</text>
      </g>
    </ArtFrame>
  )
}

/** Billing: a person checking a tablet beside a paid receipt and a usage meter. */
export function BillingArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_BillingArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#CFE2DE" }} ground={[28, 292]}>
      <g className="g-float">
        <path d="M150 46 H230 V196 L222 190 L214 196 L206 190 L198 196 L190 190 L182 196 L174 190 L166 196 L158 190 L150 196 Z" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="2.5" strokeLinejoin="round" />
        <rect x="162" y="60" width="40" height="5" rx="2.5" fill="#6B5B47" />
        <path d="M162 80 h52" stroke="#CFC6B6" strokeWidth="3" strokeLinecap="round" strokeDasharray="120" className="g-draw" style={{ animationDelay: "0s" }} />
        <rect x="208" y="78" width="12" height="3" rx="1.5" fill="#B5A58C" />
        <path d="M162 96 h40" stroke="#CFC6B6" strokeWidth="3" strokeLinecap="round" strokeDasharray="120" className="g-draw" style={{ animationDelay: "0.25s" }} />
        <rect x="208" y="94" width="12" height="3" rx="1.5" fill="#B5A58C" />
        <path d="M162 112 h46" stroke="#CFC6B6" strokeWidth="3" strokeLinecap="round" strokeDasharray="120" className="g-draw" style={{ animationDelay: "0.5s" }} />
        <rect x="208" y="110" width="12" height="3" rx="1.5" fill="#B5A58C" />
        <path d="M162 128 h34" stroke="#CFC6B6" strokeWidth="3" strokeLinecap="round" strokeDasharray="120" className="g-draw" style={{ animationDelay: "0.75s" }} />
        <rect x="208" y="126" width="12" height="3" rx="1.5" fill="#B5A58C" />
        <line x1="162" y1="148" x2="220" y2="148" stroke="#6B5B47" strokeWidth="1.5" strokeDasharray="3 3" />
        <rect x="162" y="156" width="26" height="6" rx="3" fill="#6B5B47" />
        <rect x="200" y="156" width="20" height="6" rx="3" fill="#2E9E5B" />
        <g className="g-beat" style={{ transformOrigin: "214px 178px" }}>
          <circle cx="214" cy="178" r="11" fill="none" stroke="#2E9E5B" strokeWidth="2.5" />
          <path d="M209 178 l3.5 3.5 l6 -7" stroke="#2E9E5B" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      </g>
      <path d="M238 120 A30 30 0 0 1 298 120" stroke="#F7F4EC" strokeWidth="9" fill="none" strokeLinecap="round" />
      <path d="M238 120 A30 30 0 0 1 250.8 95.4" stroke="#2E9E5B" strokeWidth="9" fill="none" strokeLinecap="round" />
      <g>
        <line x1="268" y1="120" x2="268" y2="96" stroke="#26282C" strokeWidth="3" strokeLinecap="round" />
        <animateTransform attributeName="transform" type="rotate" values="-70 268 120;-40 268 120;-62 268 120;-70 268 120" dur="5s" repeatCount="indefinite" />
      </g>
      <circle cx="268" cy="120" r="4" fill="#26282C" />
      <rect x="252" y="130" width="32" height="6" rx="3" fill="#6B5B47" opacity=".55" />
      <g transform="translate(104 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(-6 -4 164)" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(8 4 164)" />
        <path d="M-12 124 Q1 116 14 124 L16 168 L-14 168 Z" fill="#C9A24B" />
        <path d="M-8 129 L4 146 L16 140" fill="none" stroke="#C9A24B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="16" cy="140" r="3.2" fill="#B98563" />
        <path d="M10 128 L20 144 L18 140" fill="none" stroke="#C9A24B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="20" cy="141" r="3.2" fill="#B98563" />
        <circle cx="1" cy="106" r="10" fill="#B98563" />
        <path d="M-9.5 105 A10.5 10.5 0 0 1 11.5 105 Q3 97 -9.5 105 Z" fill="#3A2A20" />
      </g>
      <rect x="112" y="128" width="22" height="16" rx="2.5" fill="#26282C" transform="rotate(-14 123 136)" />
      <rect x="115" y="131" width="16" height="10" rx="1.5" fill="#9FD3B4" transform="rotate(-14 123 136)" />
      <path d="M60 70 l2.6 6.4 6.4 2.6 -6.4 2.6 -2.6 6.4 -2.6 -6.4 -6.4 -2.6 6.4 -2.6z" fill="#C9A24B" className="g-twinkle" />
      <rect x="45" y="196" width="18" height="18" rx="2" fill="#B5654A" />
      <path d="M54 196 C 52 180 46 172 42 166" stroke="#5E7A5C" strokeWidth="2" fill="none" />
      <path d="M42 166 C 32 160 40 176 50 180 Z" fill="#7C8F6B" className="g-bob" />
      <path d="M54 196 C 58 182 68 174 70 170 Z" fill="#5E7A5C" />
    </ArtFrame>
  )
}

/** Organizations: three offices linked by a path, the middle one current. */
export function OrganizationsArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_OrganizationsArt} wash={{ cx: 164, cy: 128, rx: 140, ry: 108, fill: "#EBD5CC" }} ground={[28, 292]}>
      <path id="org-arc" d="M150 96 Q 178 54 206 76 Q 234 40 264 90" stroke="#9C8C74" strokeWidth="2" fill="none" strokeDasharray="5 6" className="g-flow" />
      <circle r="4.5" fill="#2E9E5B">
        <animateMotion dur="4.5s" repeatCount="indefinite" path="M150 96 Q 178 54 206 76 Q 234 40 264 90" />
      </circle>
      <g className="g-float" style={{ animationDelay: "-2s" }}>
        <rect x="132" y="100" width="36" height="114" rx="4" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="2.5" />
        <rect x="140" y="110" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="152" y="110" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="140" y="126" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="152" y="126" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="140" y="142" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="152" y="142" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="140" y="158" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="152" y="158" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="140" y="174" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="152" y="174" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="145" y="200" width="10" height="14" rx="1.5" fill="#6B5B47" />
      </g>
      <g className="g-float" style={{ animationDelay: "-1.33333s" }}>
        <rect x="186" y="80" width="40" height="134" rx="4" fill="#F7F4EC" stroke="#2E9E5B" strokeWidth="3" />
        <rect x="194" y="90" width="8" height="9" rx="1.5" fill="#C9A24B" className="g-twinkle" style={{ animationDelay: "0s" }} />
        <rect x="210" y="90" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="194" y="106" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="210" y="106" width="8" height="9" rx="1.5" fill="#C9A24B" className="g-twinkle" style={{ animationDelay: "-0.7s" }} />
        <rect x="194" y="122" width="8" height="9" rx="1.5" fill="#C9A24B" className="g-twinkle" style={{ animationDelay: "-1.4s" }} />
        <rect x="210" y="122" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="194" y="138" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="210" y="138" width="8" height="9" rx="1.5" fill="#C9A24B" className="g-twinkle" style={{ animationDelay: "-2.1s" }} />
        <rect x="194" y="154" width="8" height="9" rx="1.5" fill="#C9A24B" className="g-twinkle" style={{ animationDelay: "-2.8s" }} />
        <rect x="210" y="154" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="194" y="170" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="210" y="170" width="8" height="9" rx="1.5" fill="#C9A24B" className="g-twinkle" style={{ animationDelay: "-3.5s" }} />
        <rect x="201" y="200" width="10" height="14" rx="1.5" fill="#6B5B47" />
        <circle cx="226" cy="80" r="9" fill="#2E9E5B" className="g-pulse" />
        <path d="M221 80 l3.5 3.5 l6 -7" stroke="#FFFFFF" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <g className="g-float" style={{ animationDelay: "-2s" }}>
        <rect x="244" y="94" width="40" height="120" rx="4" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="2.5" />
        <rect x="252" y="104" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="268" y="104" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="252" y="120" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="268" y="120" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="252" y="136" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="268" y="136" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="252" y="152" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="268" y="152" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="252" y="168" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="268" y="168" width="8" height="9" rx="1.5" fill="#D8CFC0" />
        <rect x="259" y="200" width="10" height="14" rx="1.5" fill="#6B5B47" />
      </g>
      <g className="g-float" style={{ animationDelay: "-1.4s" }}>
        <rect x="58" y="52" width="66" height="26" rx="13" fill="#FBF8F1" stroke="#CFC6B6" />
        <circle cx="72" cy="65" r="6" fill="#4A6A8E" />
        <path d="M84 61 h22 l-4 -3 M106 69 h-22 l4 3" stroke="#6B5B47" strokeWidth="1.8" fill="none" strokeLinecap="round" />
      </g>
      <path d="M90 122 Q 116 92 146 100" stroke="#9C8C74" strokeWidth="2" fill="none" strokeDasharray="3 5" className="g-flow" />
      <g className="g-float" style={{ animationDelay: "-2.1s" }}>
        <rect x="62" y="124" width="40" height="90" rx="4" fill="#F7F4EC" fillOpacity=".55" stroke="#9C8C74" strokeWidth="2" strokeDasharray="5 4" />
        <g className="g-beat" style={{ transformOrigin: "82px 164px" }}>
          <circle cx="82" cy="164" r="11" fill="#2E9E5B" />
          <path d="M82 158 v12 M76 164 h12" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
        </g>
      </g>
      <rect x="287" y="196" width="18" height="18" rx="2" fill="#B5654A" />
      <path d="M296 196 C 294 180 288 172 284 166" stroke="#5E7A5C" strokeWidth="2" fill="none" />
      <path d="M284 166 C 274 160 282 176 292 180 Z" fill="#7C8F6B" className="g-bob" />
      <path d="M296 196 C 300 182 310 174 312 170 Z" fill="#5E7A5C" />
    </ArtFrame>
  )
}

/** Security: a shield with a green padlock inside a dashed ring. */
export function SecurityArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_SecurityArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#D6E2E8" }} ground={[28, 292]}>
      <circle cx="160" cy="124" r="78" fill="none" stroke="#9C8C74" strokeWidth="1.6" strokeDasharray="4 7" className="g-flow" />
      <path d="M160 52 L214 72 V118 C214 156 190 180 160 194 C130 180 106 156 106 118 V72 Z" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="3" strokeLinejoin="round" />
      <path d="M160 64 L204 80 V118 C204 150 184 170 160 182 Z" fill="#E9E2D3" />
      <path d="M146 118 V106 a14 14 0 0 1 28 0 V118" stroke="#26282C" strokeWidth="5" fill="none" strokeLinecap="round" />
      <rect x="138" y="116" width="44" height="36" rx="6" fill="#2E9E5B" />
      <circle cx="160" cy="131" r="5" fill="#F7F4EC" />
      <rect x="158" y="133" width="4" height="10" rx="2" fill="#F7F4EC" />
      <g className="g-float">
        <rect x="40" y="68" width="50" height="30" rx="7" fill="#FBF8F1" stroke="#CFC6B6" />
        <circle cx="52" cy="83" r="3.4" fill="#26282C" className="g-twinkle" style={{ animationDelay: "0s" }} />
        <circle cx="61" cy="83" r="3.4" fill="#26282C" className="g-twinkle" style={{ animationDelay: "-0.4s" }} />
        <circle cx="70" cy="83" r="3.4" fill="#26282C" className="g-twinkle" style={{ animationDelay: "-0.8s" }} />
        <circle cx="79" cy="83" r="3.4" fill="#26282C" className="g-twinkle" style={{ animationDelay: "-1.2s" }} />
      </g>
      <g className="g-float" style={{ animationDelay: "-1.6s" }}>
        <circle cx="252" cy="78" r="18" fill="#FBF8F1" stroke="#CFC6B6" />
        <circle cx="252" cy="78" r="11" fill="none" stroke="#4A6A8E" strokeWidth="2" />
        <path d="M241 78 h22 M252 67 c5 5 5 17 0 22 c-5 -5 -5 -17 0 -22" stroke="#4A6A8E" strokeWidth="1.8" fill="none" />
      </g>
      <g className="g-float" style={{ animationDelay: "-0.8s" }}>
        <circle cx="258" cy="168" r="17" fill="#FBF8F1" stroke="#CFC6B6" />
        <circle cx="258" cy="168" r="10" fill="none" stroke="#B5654A" strokeWidth="2" />
        <g className="g-spin" style={{ transformOrigin: "258px 168px" }}>
          <line x1="258" y1="168" x2="258" y2="161" stroke="#B5654A" strokeWidth="2" strokeLinecap="round" />
        </g>
      </g>
      <g className="g-beat" style={{ transformOrigin: "66px 166px" }}>
        <circle cx="66" cy="166" r="13" fill="#2E9E5B" />
        <path d="M60 166 l4 4 l8 -9" stroke="#FFFFFF" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
    </ArtFrame>
  )
}

/** Team: two teammates sending an invite to a new teammate in a doorway. */
export function TeamInviteArt({ label }: { label?: string }) {
  return (
    <ArtFrame label={label ?? LABEL_TeamInviteArt} wash={{ cx: 160, cy: 128, rx: 140, ry: 108, fill: "#E0DAEC" }} ground={[28, 292]}>
      <rect x="232" y="78" width="54" height="136" rx="3" fill="#F7F4EC" stroke="#6B5B47" strokeWidth="3" />
      <rect x="240" y="86" width="38" height="128" fill="#FBEFD9" />
      <circle cx="272" cy="152" r="2.5" fill="#6B5B47" />
      <path d="M118 92 Q 178 34 238 92" stroke="#9C8C74" strokeWidth="2" fill="none" strokeDasharray="5 6" className="g-flow" />
      <g>
        <g>
          <rect x="-11" y="-8" width="22" height="16" rx="2.5" fill="#F7F4EC" stroke="#26282C" strokeWidth="1.6" />
          <path d="M-10 -6 L0 2 L10 -6" stroke="#26282C" strokeWidth="1.6" fill="none" strokeLinejoin="round" />
        </g>
        <animateMotion dur="4.8s" repeatCount="indefinite" rotate="0" path="M118 92 Q 178 34 238 92" />
      </g>
      <g transform="translate(64 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(-6 -4 164)" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(8 4 164)" />
        <path d="M-12 124 Q1 116 14 124 L16 168 L-14 168 Z" fill="#7C8F6B" />
        <path d="M-8 129 L-10 148 L-8 162" fill="none" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-8" cy="163" r="3.2" fill="#D6AB86" />
        <path d="M10 128 L14 148 L12 162" fill="none" stroke="#7C8F6B" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="12" cy="163" r="3.2" fill="#D6AB86" />
        <circle cx="1" cy="106" r="10" fill="#D6AB86" />
        <path d="M-9.5 105 A10.5 10.5 0 0 1 11.5 105 Q3 97 -9.5 105 Z" fill="#2E231D" />
        <circle cx="-7" cy="97" r="4.5" fill="#2E231D" />
      </g>
      <g transform="translate(104 0)">
        <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(-6 -4 164)" />
        <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(8 4 164)" />
        <path d="M-12 124 Q1 116 14 124 L16 168 L-14 168 Z" fill="#4A6A8E" />
        <path d="M-8 129 L-12 148 L-10 162" fill="none" stroke="#4A6A8E" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="-10" cy="163" r="3.2" fill="#B98563" />
        <path d="M10 128 L22 112 L32 98" fill="none" stroke="#4A6A8E" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="34" cy="97" r="3.2" fill="#B98563" />
        <circle cx="1" cy="106" r="10" fill="#B98563" />
        <path d="M-9.5 105 A10.5 10.5 0 0 1 11.5 105 Q3 97 -9.5 105 Z" fill="#3A2A20" />
      </g>
      <g className="g-nudge">
        <g transform="translate(258 0)">
          <rect x="-8" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(-6 -4 164)" />
          <rect x="1" y="164" width="7" height="50" rx="3" fill="#26282C" transform="rotate(8 4 164)" />
          <path d="M-12 124 Q1 116 14 124 L16 168 L-14 168 Z" fill="#B5654A" />
          <path d="M-8 129 L-20 116 L-26 102" fill="none" stroke="#B5654A" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="-27" cy="101" r="3.2" fill="#E0B892" />
          <path d="M10 128 L12 148 L10 162" fill="none" stroke="#B5654A" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="10" cy="163" r="3.2" fill="#E0B892" />
          <circle cx="1" cy="106" r="10" fill="#E0B892" />
          <path d="M-9.5 105 A10.5 10.5 0 0 1 11.5 105 Q3 97 -9.5 105 Z" fill="#2E231D" />
          <circle cx="-7" cy="97" r="4.5" fill="#2E231D" />
        </g>
      </g>
      <g className="g-beat" style={{ transformOrigin: "286px 70px" }}>
        <circle cx="286" cy="70" r="11" fill="#2E9E5B" />
        <path d="M286 64 v12 M280 70 h12" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" />
      </g>
      <path d="M150 58 l2.6 6.4 6.4 2.6 -6.4 2.6 -2.6 6.4 -2.6 -6.4 -6.4 -2.6 6.4 -2.6z" fill="#C9A24B" className="g-twinkle" />
      <rect x="155" y="196" width="18" height="18" rx="2" fill="#B5654A" />
      <path d="M164 196 C 162 180 156 172 152 166" stroke="#5E7A5C" strokeWidth="2" fill="none" />
      <path d="M152 166 C 142 160 150 176 160 180 Z" fill="#7C8F6B" className="g-bob" />
      <path d="M164 196 C 168 182 178 174 180 170 Z" fill="#5E7A5C" />
    </ArtFrame>
  )
}
/** The short card frame (320 by 170) used under the Schedules calendar: wash, dot field and grain. */
function CardArtFrame({ label, wash, children }: { label: string; wash: { cx: number; cy: number; rx: number; ry: number; fill: string }; children: ReactNode }) {
  const raw = useId()
  const id = `dc${raw.replace(/[^a-zA-Z0-9]/g, "")}`
  return (
    <div className="ag-art">
      <svg role="img" aria-label={label} viewBox="0 0 320 170" preserveAspectRatio="xMidYMid slice">
        <defs>
          <filter id={`${id}b`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="18" />
          </filter>
          <pattern id={`${id}d`} width="9" height="9" patternUnits="userSpaceOnUse">
            <circle cx="1.8" cy="1.8" r="0.9" fill="#262826" />
          </pattern>
          <linearGradient id={`${id}f`} x1="0" x2="1">
            <stop offset="0.3" stopColor="#FFFFFF" stopOpacity="0" />
            <stop offset="1" stopColor="#FFFFFF" stopOpacity="1" />
          </linearGradient>
          <mask id={`${id}m`}>
            <rect width="320" height="170" fill={`url(#${id}f)`} />
          </mask>
          <filter id={`${id}g`} x="0" y="0" width="100%" height="100%">
            <feTurbulence type="fractalNoise" baseFrequency="1.1" numOctaves={2} stitchTiles="stitch" />
            <feColorMatrix values="0 0 0 0 0.15 0 0 0 0 0.13 0 0 0 0 0.1 0.9 0 0 0 -0.4" />
          </filter>
        </defs>
        <rect width="320" height="170" fill="#E7ECE3" />
        <g filter={`url(#${id}b)`}>
          <circle className="g-mesh" cx="40" cy="14" r="90" fill="#CFDCCB" opacity="0.9" />
          <ellipse cx={wash.cx} cy={wash.cy} rx={wash.rx} ry={wash.ry} fill={wash.fill} />
          <circle className="g-mesh" cx="296" cy="160" r="80" fill="#EBDCC0" opacity="0.8" style={{ animationDelay: "-8s" }} />
        </g>
        <rect width="320" height="170" fill={`url(#${id}d)`} opacity="0.2" mask={`url(#${id}m)`} />
        {children}
        <rect width="320" height="170" filter={`url(#${id}g)`} opacity="0.45" />
      </svg>
    </div>
  )
}

function AppTile({ y, code, tone }: { y: number; code: string; tone: "green" | "amber" }) {
  return (
    <g>
      <rect x="36" y={y} width="30" height="30" rx="8" fill="#FBF1DC" stroke="#D9D1C2" strokeWidth="1.5" />
      <text x="51" y={y + 19} textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="9.5" fontWeight="600" fill="#33342F">
        {code.slice(0, 2).toUpperCase()}
      </text>
      <circle cx="64" cy={y + 2} r="4.5" fill={tone === "green" ? "#19C37D" : "#E2A33A"} stroke="#FBF1DC" strokeWidth="1.5" />
    </g>
  )
}

/**
 * Schedules: connectors wired into the Gravitre hub. With a broken sign in, the
 * bottom link is cut by a padlock and its runs queue up in amber with their count.
 */
export function ConnectionsQueueArt({ broken, queued, apps }: { broken: boolean; queued?: number; apps?: [string, string, string] }) {
  const [a, b, c] = apps ?? ["GS", "SL", "HS"]
  return (
    <CardArtFrame
      label={
        broken
          ? `Connectors linked to a central hub, one link broken by an expired sign in${queued ? `, with ${queued} runs waiting` : ""}`
          : "Connectors linked to a central hub, every link signed in"
      }
      wash={{ cx: 170, cy: 96, rx: 130, ry: 70, fill: "#D9DEE3" }}
    >
      <g fill="none" stroke="#7E9A7B" strokeWidth="2" strokeLinecap="round">
        <path d="M66 40 C 110 40 120 80 146 84" />
        <path d="M66 86 H146" />
        <path className="g-flow" d="M174 86 H222" strokeDasharray="3 5" />
        <path className="g-flow" d="M174 88 C 200 96 206 126 222 130" strokeDasharray="3 5" />
        {broken ? null : <path d="M66 132 C 96 132 120 96 146 90" />}
      </g>
      {broken ? (
        <>
          <path d="M66 132 C 96 132 104 116 116 110" fill="none" stroke="#B5654A" strokeWidth="2" strokeLinecap="round" />
          <path d="M128 102 C 136 96 140 92 146 90" fill="none" stroke="#B5654A" strokeWidth="2" strokeLinecap="round" strokeDasharray="2 4" />
          <g className="g-pulse">
            <circle cx="122" cy="106" r="10" fill="#FBF1DC" stroke="#E2A33A" strokeWidth="1.5" />
            <rect x="117.5" y="105" width="9" height="7" rx="1.5" fill="#8A5A06" />
            <path d="M119.5 105v-2.2a2.5 2.5 0 0 1 5 0V105" fill="none" stroke="#8A5A06" strokeWidth="1.5" />
          </g>
        </>
      ) : null}
      <AppTile y={25} code={a} tone="green" />
      <AppTile y={71} code={b} tone="green" />
      <AppTile y={117} code={c} tone={broken ? "amber" : "green"} />
      <circle cx="160" cy="86" r="16" fill="#141513" />
      <g transform="translate(150.5 79.5) scale(0.63)">
        <path d="M7 0h23l-4 6H3z M5 8h22l-4 6H1z M3 16h20l-4 6H0z" fill="#19C37D" />
      </g>
      <g className="g-float">
        <rect x="226" y="72" width="66" height="26" rx="13" fill="#FBF1DC" stroke="#D9D1C2" strokeWidth="1.5" />
        <circle cx="240" cy="85" r="4" fill="#19C37D" />
        <rect x="250" y="82.5" width="32" height="5" rx="2.5" fill="#C9C4B8" />
      </g>
      <rect x="232" y="132" width="66" height="26" rx="13" fill="#FBF1DC" stroke="#D9D1C2" strokeWidth="1.5" opacity="0.6" />
      <rect x="229" y="125" width="66" height="26" rx="13" fill="#FBF1DC" stroke="#D9D1C2" strokeWidth="1.5" opacity="0.8" />
      <g>
        <rect x="226" y="118" width="66" height="26" rx="13" fill="#FBF1DC" stroke={broken ? "#E2A33A" : "#D9D1C2"} strokeWidth="1.5" />
        <circle cx="240" cy="131" r="4" fill={broken ? "#E2A33A" : "#19C37D"} />
        {broken && queued ? (
          <text x="266" y="135" textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="10" fontWeight="600" fill="#8A5A06">
            {queued > 99 ? "99+" : queued}
          </text>
        ) : (
          <rect x="250" y="128.5" width="32" height="5" rx="2.5" fill="#C9C4B8" />
        )}
      </g>
    </CardArtFrame>
  )
}

function minutesOf(hhmm: string): number {
  const [h, m] = hhmm.split(":").map((part) => Number.parseInt(part, 10))
  return ((Number.isFinite(h) ? h : 0) % 24) * 60 + (Number.isFinite(m) ? m : 0)
}

/** A point on the 24 hour dial (00 at the top, clockwise). */
function dialPoint(minutes: number, r: number): [number, number] {
  const a = (minutes / 1440) * Math.PI * 2 - Math.PI / 2
  return [132 + r * Math.cos(a), 88 + r * Math.sin(a)]
}

/**
 * Quiet hours: a 24 hour dial with the quiet window shaded and messages waiting
 * for the end of it. Off, the dial has no shading and the clock tag reads Off.
 */
export function QuietHoursArt({ enabled, from, to }: { enabled: boolean; from: string; to: string }) {
  const start = minutesOf(from)
  const end = minutesOf(to)
  const span = (end - start + 1440) % 1440
  const [sx, sy] = dialPoint(start, 44)
  const [ex, ey] = dialPoint(end, 44)
  const [mx, my] = dialPoint(start, 58)
  const [ux, uy] = dialPoint(end, 58)
  const now = new Date()
  const hand = dialPoint(now.getHours() * 60 + now.getMinutes(), 32)
  return (
    <CardArtFrame
      label={enabled ? `A 24 hour dial with quiet hours from ${from} to ${to} shaded, messages waiting until ${to}` : "A 24 hour dial with quiet hours turned off"}
      wash={{ cx: 150, cy: 96, rx: 120, ry: 72, fill: "#DCE3E8" }}
    >
      <circle cx="132" cy="88" r="52" fill="#FBF1DC" stroke="#D9D1C2" strokeWidth="2" />
      {enabled && span > 0 ? (
        <path
          d={`M${sx.toFixed(1)} ${sy.toFixed(1)} A44 44 0 ${span > 720 ? 1 : 0} 1 ${ex.toFixed(1)} ${ey.toFixed(1)}`}
          fill="none"
          stroke="#5B6E7A"
          strokeOpacity="0.35"
          strokeWidth="14"
          strokeLinecap="round"
        />
      ) : null}
      {Array.from({ length: 24 }, (_, hour) => {
        const major = hour % 6 === 0
        const [x1, y1] = dialPoint(hour * 60, 50)
        const [x2, y2] = dialPoint(hour * 60, major ? 45 : 48)
        return (
          <line
            key={hour}
            x1={x1.toFixed(1)}
            y1={y1.toFixed(1)}
            x2={x2.toFixed(1)}
            y2={y2.toFixed(1)}
            stroke="#33342F"
            strokeWidth={major ? 1.6 : 1}
            strokeLinecap="round"
          />
        )
      })}
      <text x="132" y="56" textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="8.5" fill="#55564F">
        00
      </text>
      <text x="132" y="127" textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="8.5" fill="#55564F">
        12
      </text>
      <line x1="132" y1="88" x2={hand[0].toFixed(1)} y2={hand[1].toFixed(1)} stroke="#141513" strokeWidth="2.4" strokeLinecap="round" />
      <circle cx="132" cy="88" r="3.5" fill="#141513" />
      {enabled ? (
        <>
          <g transform={`translate(${mx.toFixed(1)} ${my.toFixed(1)})`}>
            <path d="M5 -7a8 8 0 1 0 6 11a6.5 6.5 0 0 1 -6 -11z" fill="#5B6E7A" />
          </g>
          <g transform={`translate(${ux.toFixed(1)} ${uy.toFixed(1)})`}>
            <circle r="5.5" fill="#E2A33A" />
          </g>
        </>
      ) : null}
      <g className="g-float">
        <rect x="214" y="52" width="80" height="26" rx="13" fill="#FBF1DC" stroke="#D9D1C2" strokeWidth="1.5" />
        <path d="M226 60h12v9h-12z M226 60l6 5 6-5" fill="none" stroke="#5B6E7A" strokeWidth="1.4" strokeLinejoin="round" />
        <rect x="244" y="62.5" width="38" height="5" rx="2.5" fill="#C9C4B8" />
      </g>
      <g className="g-float" style={{ animationDelay: "-2.4s" }}>
        <rect x="214" y="86" width="80" height="26" rx="13" fill="#FBF1DC" stroke="#D9D1C2" strokeWidth="1.5" />
        <path d="M226 94h12v9h-12z M226 94l6 5 6-5" fill="none" stroke="#5B6E7A" strokeWidth="1.4" strokeLinejoin="round" />
        <rect x="244" y="96.5" width="30" height="5" rx="2.5" fill="#C9C4B8" />
      </g>
      <g>
        <rect x="214" y="122" width="80" height="24" rx="12" fill="#141513" />
        <circle cx="227" cy="134" r="3.5" fill={enabled ? "#E2A33A" : "#8A8B85"} />
        <text x="261" y="138" textAnchor="middle" fontFamily="Geist Mono, monospace" fontSize="10" fontWeight="600" fill="#EFEFEA">
          {enabled ? to : "Off"}
        </text>
      </g>
    </CardArtFrame>
  )
}
