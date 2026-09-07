/**
 * Sharp square-cap outline glyphs for the product sidebar (Nodus Product Image style).
 * currentColor + strokeWidth so active/hover tints work (unlike <img> Nucleo sprites).
 */
import type { ReactNode, SVGProps } from "react"

type NavIconProps = SVGProps<SVGSVGElement> & {
  size?: number | string
  strokeWidth?: number | string
}

function NavSvg({
  size = 20,
  strokeWidth = 1.75,
  className,
  children,
  ...props
}: NavIconProps & { children: ReactNode }) {
  const dim = size
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={dim}
      height={dim}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden
      {...props}
    >
      <g
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="square"
        strokeLinejoin="miter"
        strokeMiterlimit={10}
      >
        {children}
      </g>
    </svg>
  )
}

/** 2×2 grid — Dashboard / Home */
export function NavGrid(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1" />
    </NavSvg>
  )
}

/** Robot head — Agents */
export function NavAgent(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M8 4.5V3M16 4.5V3" />
      <rect x="4.5" y="5.5" width="15" height="13" rx="2" />
      <circle cx="9.5" cy="11" r="1.25" fill="currentColor" stroke="none" />
      <circle cx="14.5" cy="11" r="1.25" fill="currentColor" stroke="none" />
      <path d="M9.5 15h5" />
    </NavSvg>
  )
}

/** Branching nodes — Workflows */
export function NavWorkflow(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <rect x="3.5" y="3.5" width="5" height="5" rx="0.75" />
      <rect x="3.5" y="15.5" width="5" height="5" rx="0.75" />
      <rect x="15.5" y="9.5" width="5" height="5" rx="0.75" />
      <path d="M8.5 6h3.5v10H8.5M12 11h3.5" />
    </NavSvg>
  )
}

/** List + check — Assignments / Tasks */
export function NavTasks(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M4 6h10M4 11h8M4 16h6" />
      <path d="M14.5 14.5l2 2 4-4.5" />
    </NavSvg>
  )
}

/** Plug — Connectors / Apps */
export function NavPlug(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M8 2.5v5M16 2.5v5" />
      <path d="M4.5 7.5h15" />
      <path d="M5.5 7.5v3.2c0 3.2 2.2 5.8 5.2 6.5V21.5h2.6v-4.3c3-0.7 5.2-3.3 5.2-6.5V7.5" />
    </NavSvg>
  )
}

/** Bell — Notifications / Approvals cue */
export function NavBell(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M6 16.5h12l-1.2-1.4V10a4.8 4.8 0 0 0-9.6 0v5.1L6 16.5z" />
      <path d="M10.2 18.5a1.8 1.8 0 0 0 3.6 0" />
    </NavSvg>
  )
}

/** Chat bubble */
export function NavChat(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M5 5.5h14a1.5 1.5 0 0 1 1.5 1.5v8a1.5 1.5 0 0 1-1.5 1.5H10l-4 3v-3H5A1.5 1.5 0 0 1 3.5 15V7A1.5 1.5 0 0 1 5 5.5z" />
    </NavSvg>
  )
}

/** Target — Goals */
export function NavTarget(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1.25" fill="currentColor" stroke="none" />
    </NavSvg>
  )
}

/** Database — Sources */
export function NavDatabase(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <ellipse cx="12" cy="6" rx="7.5" ry="2.5" />
      <path d="M4.5 6v12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5V6" />
      <path d="M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5" />
    </NavSvg>
  )
}

/** Calendar — Schedules */
export function NavCalendar(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <rect x="3.5" y="5.5" width="17" height="15" rx="1.5" />
      <path d="M3.5 10h17M8 3.5v4M16 3.5v4" />
    </NavSvg>
  )
}

/** Activity pulse / check */
export function NavActivity(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8 12.2l2.4 2.4L16.2 9" />
    </NavSvg>
  )
}

/** Marketplace / package */
export function NavPackage(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M3.5 8.5 12 4l8.5 4.5v9L12 22l-8.5-4.5v-9z" />
      <path d="M12 4v18M3.5 8.5 12 13l8.5-4.5" />
    </NavSvg>
  )
}

/** Shield check — Approvals */
export function NavApproval(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M12 3.5 19.5 6.5v5.2c0 4.4-2.9 7.6-7.5 9.3-4.6-1.7-7.5-4.9-7.5-9.3V6.5L12 3.5z" />
      <path d="M9 12.2l2.2 2.2L15.5 10" />
    </NavSvg>
  )
}

/** Sliders — Settings */
export function NavSliders(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
      <circle cx="8" cy="7" r="1.75" fill="currentColor" stroke="none" />
      <circle cx="15" cy="12" r="1.75" fill="currentColor" stroke="none" />
      <circle cx="11" cy="17" r="1.75" fill="currentColor" stroke="none" />
    </NavSvg>
  )
}

/** Chart — Metrics */
export function NavChart(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M4 19.5h16" />
      <path d="M7 16.5V11M12 16.5V7M17 16.5v-5" />
    </NavSvg>
  )
}

/** Document — Audit */
export function NavFile(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M7 3.5h7l5 5V20.5H7z" />
      <path d="M14 3.5V9h5.5M9.5 13h5M9.5 16.5h5" />
    </NavSvg>
  )
}

/** Sparkles / intelligence */
export function NavSparkles(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M12 3.5l1.4 4.2L17.5 9l-4.1 1.3L12 14.5l-1.4-4.2L6.5 9l4.1-1.3z" />
      <path d="M18.5 14.5l.7 2.1 2.1.7-2.1.7-.7 2.1-.7-2.1-2.1-.7 2.1-.7z" />
    </NavSvg>
  )
}

/** Rocket — Getting started */
export function NavRocket(props: NavIconProps) {
  return (
    <NavSvg {...props}>
      <path d="M12 3.5c2.8 1.6 5 4.6 5.5 8.2l-2.8 2.8-2.7-2.7-2.7 2.7-2.8-2.8C7 8.1 9.2 5.1 12 3.5z" />
      <path d="M9.5 16.5 7 20.5M14.5 16.5 17 20.5M10.5 19.5h3" />
    </NavSvg>
  )
}
