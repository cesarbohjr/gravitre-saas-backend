"use client"

import { useReducedMotion } from "framer-motion"
import type { RosterAgent } from "@/lib/agents-roster"
import { DEPARTMENT_ICONS } from "@/lib/department-icons"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"
import { cn } from "@/lib/utils"

/** Department hues from the global --dept-* tokens (the roster's department cards use the same). */
export const DEPT_DOT: Record<AgentDepartmentId, string> = {
  sales: "var(--dept-sales)",
  marketing: "var(--dept-marketing)",
  customer_success: "var(--dept-customer_success)",
  operations: "var(--dept-operations)",
  finance: "var(--dept-finance)",
  engineering: "var(--dept-engineering)",
  security: "var(--dept-security)",
  general: "var(--dept-general)",
}

/** Six seats around the council table: node, department label and "typing" bubble. */
const SEATS = [
  { x: 380, y: 62, label: { x: 380, y: 32, anchor: "middle" }, bubble: { x: 410, y: 22 } },
  { x: 500, y: 118, label: { x: 560, y: 122, anchor: "start" }, bubble: { x: 530, y: 78 } },
  { x: 500, y: 232, label: { x: 560, y: 236, anchor: "start" }, bubble: { x: 530, y: 192 } },
  { x: 380, y: 288, label: { x: 380, y: 330, anchor: "middle" }, bubble: { x: 410, y: 248 } },
  { x: 260, y: 232, label: { x: 200, y: 236, anchor: "end" }, bubble: { x: 196, y: 192 } },
  { x: 260, y: 118, label: { x: 200, y: 122, anchor: "end" }, bubble: { x: 196, y: 78 } },
] as const

export interface CouncilSeat {
  department: AgentDepartmentId
  departmentLabel: string
  agent: RosterAgent | null
  /** Takes part in the question being previewed. */
  involved: boolean
}

/**
 * Up to six seats, one per department: the question's departments first, then the
 * rest of your roster. Each seat shows a real agent from that department.
 */
export function councilSeats(
  agents: RosterAgent[],
  focus: AgentDepartmentId[],
  labels: Map<AgentDepartmentId, string>,
): CouncilSeat[] {
  const byDept = new Map<AgentDepartmentId, RosterAgent[]>()
  for (const a of agents) {
    if (a.state === "not_set_up") continue
    const list = byDept.get(a.department) ?? []
    list.push(a)
    byDept.set(a.department, list)
  }
  const order: AgentDepartmentId[] = []
  for (const d of focus) if (!order.includes(d)) order.push(d)
  for (const d of byDept.keys()) if (!order.includes(d)) order.push(d)
  return order.slice(0, 6).map((department) => {
    const pool = (byDept.get(department) ?? []).slice().sort((x, y) => {
      const rank = (a: RosterAgent) => (a.state === "blocked" ? 1 : 0)
      return rank(x) - rank(y) || y.tasksToday - x.tasksToday || x.name.localeCompare(y.name)
    })
    return {
      department,
      departmentLabel: labels.get(department) ?? department,
      agent: pool[0] ?? null,
      involved: focus.length === 0 || focus.includes(department),
    }
  })
}

export function CouncilPreview({ seats, className }: { seats: CouncilSeat[]; className?: string }) {
  const reduced = useReducedMotion()
  const animate = !reduced
  const placed = seats.map((seat, i) => ({ seat, pos: SEATS[i] }))
  const names = seats.filter((s) => s.agent).map((s) => `${s.agent?.name} (${s.departmentLabel})`)
  const label =
    names.length > 0
      ? `Council preview: an objective goes to ${names.join(", ")}, who message each other around the table, then one recommendation comes out`
      : "Council preview: an objective goes to a council of agents, then one recommendation comes out"

  return (
    <svg role="img" aria-label={label} viewBox="0 0 760 350" className={className}>
      <g fill="none" strokeWidth="1.4" strokeDasharray="3 5" className="ma-svg-edge">
        {animate ? <animate attributeName="stroke-dashoffset" from="16" to="0" dur="1.2s" repeatCount="indefinite" /> : null}
        {/* Ring edges between neighbouring seats; it only closes when all six are filled. */}
        {placed.map(({ pos }, i) => {
          const next = i + 1 < placed.length ? placed[i + 1].pos : placed.length === SEATS.length ? placed[0].pos : null
          return next ? <path key={`e${i}`} d={`M${pos.x} ${pos.y} L${next.x} ${next.y}`} /> : null
        })}
        {placed.map(({ pos, seat }, i) => (
          <path
            key={`s${i}`}
            d={`M${pos.x} ${pos.y} L380 175`}
            stroke={seat.involved && seat.agent ? "#7cc49b" : undefined}
            strokeWidth={seat.involved && seat.agent ? 1.8 : 1.4}
          />
        ))}
        <path d="M84 175 L342 175" />
        <path d="M418 175 L676 175" />
      </g>

      {animate ? (
        <circle cx="380" cy="175" r="38" fill="none" stroke="#2e9e5b" strokeWidth="1.5">
          <animate attributeName="r" values="38;52" dur="2.6s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.6;0" dur="2.6s" repeatCount="indefinite" />
        </circle>
      ) : null}
      <circle cx="380" cy="175" r="36" className="ma-svg-council" stroke="#2e9e5b" strokeWidth="1.8" />
      <g fill="none" stroke="#2e9e5b" strokeWidth="1.5" strokeLinecap="round">
        <circle cx="380" cy="161" r="5" />
        <path d="M370 180 Q380 168 390 180" />
        <circle cx="367" cy="165" r="3.5" />
        <circle cx="393" cy="165" r="3.5" />
      </g>
      <text x="380" y="198" textAnchor="middle" fontSize="11" fontWeight="600" fill="#2e9e5b">
        Council
      </text>

      {placed.map(({ seat, pos }, i) => (
        <g key={`n${seat.department}`} transform={`translate(${pos.x} ${pos.y})`} className={cn(!seat.involved && "ma-seat-dim")}>
          <rect
            x="-22"
            y="-22"
            width="44"
            height="44"
            rx="12"
            className="ma-svg-node"
            strokeDasharray={seat.agent ? undefined : "3 3"}
          />
          {animate && seat.agent && seat.involved ? (
            <rect x="-25" y="-25" width="50" height="50" rx="14" fill="none" stroke="#2e9e5b" strokeWidth="1.5" opacity="0">
              <animate
                attributeName="opacity"
                values="0;1;1;0;0"
                keyTimes="0;0.1;0.4;0.5;1"
                dur="6s"
                begin={`${i}s`}
                repeatCount="indefinite"
              />
            </rect>
          ) : null}
          {seat.agent ? (
            <SeatIcon department={seat.department} />
          ) : (
            <text y="5" textAnchor="middle" fontSize="14" fontWeight="600" className="ma-svg-ink">
              +
            </text>
          )}
          {seat.agent ? (
            <circle
              cx="19"
              cy="19"
              r="5"
              fill={seat.agent.state === "blocked" ? "#e2a33a" : "#2e9e5b"}
              stroke="#ffffff"
              strokeWidth="2"
            />
          ) : null}
          <title>
            {seat.agent ? `${seat.agent.name}, ${seat.departmentLabel}` : `No ${seat.departmentLabel} agent yet`}
          </title>
        </g>
      ))}

      <g fontSize="11" className="ma-svg-text">
        {placed.map(({ seat, pos }) => (
          <text key={`l${seat.department}`} x={pos.label.x} y={pos.label.y} textAnchor={pos.label.anchor}>
            {seat.departmentLabel}
          </text>
        ))}
      </g>

      {animate
        ? placed.map(({ seat, pos }, i) =>
            seat.agent && seat.involved ? (
              <g key={`b${seat.department}`} transform={`translate(${pos.bubble.x} ${pos.bubble.y})`} opacity="0">
                <animate
                  attributeName="opacity"
                  values="0;1;1;0;0"
                  keyTimes="0;0.1;0.4;0.5;1"
                  dur="6s"
                  begin={`${i}s`}
                  repeatCount="indefinite"
                />
                <rect width="34" height="18" rx="9" className="ma-svg-card" />
                <circle cx="10" cy="9" r="1.8" className="ma-svg-text" />
                <circle cx="17" cy="9" r="1.8" className="ma-svg-text" />
                <circle cx="24" cy="9" r="1.8" className="ma-svg-text" />
              </g>
            ) : null,
          )
        : null}

      <circle cx="60" cy="175" r="22" className="ma-svg-target" strokeWidth="1.6" />
      <circle cx="60" cy="175" r="12" fill="none" className="ma-svg-target" strokeWidth="1.6" />
      <circle cx="60" cy="175" r="6.5" fill="none" className="ma-svg-target" strokeWidth="1.6" />
      <circle cx="60" cy="175" r="2" className="ma-svg-ink" />
      <text x="60" y="216" textAnchor="middle" fontSize="13" className="ma-svg-ink">
        Objective
      </text>

      {animate ? (
        <circle cx="700" cy="175" r="24" fill="none" stroke="#2e9e5b" strokeWidth="1.5">
          <animate attributeName="r" values="24;34" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.7;0" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
        </circle>
      ) : null}
      <circle cx="700" cy="175" r="22" className="ma-svg-card" stroke="#2e9e5b" strokeWidth="1.6" />
      <g fill="none" stroke="#2e9e5b" strokeWidth="1.6" strokeLinejoin="round">
        <path d="M700 164 L711 170 L700 176 L689 170 Z" />
        <path d="M689 175 L700 181 L711 175" />
        <path d="M689 180 L700 186 L711 180" />
      </g>
      <text x="700" y="216" textAnchor="middle" fontSize="13" fill="#2e9e5b">
        Recommendation
      </text>
    </svg>
  )
}

function SeatIcon({ department }: { department: AgentDepartmentId }) {
  const Icon = DEPARTMENT_ICONS[department] ?? DEPARTMENT_ICONS.general
  return <Icon x={-11} y={-11} width={22} height={22} strokeWidth={1.9} className="dept-glyph" data-dept={department} aria-hidden />
}
