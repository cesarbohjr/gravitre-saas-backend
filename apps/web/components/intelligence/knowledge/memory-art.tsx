/**
 * Animated empty-state art from the 10-30 Knowledge · Memory design: facts
 * drift into the memory, the ring fills and the stack lights up, then a check.
 * Decorative only.
 */
import "@/components/intelligence/shell/intel-motion.css"

export function MemoryArt() {
  return (
    <div className="m2-art" aria-hidden>
      <svg viewBox="0 0 260 118" style={{ width: "100%", height: "100%", display: "block" }}>
        <defs>
          <radialGradient id="m2Glow" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#DDF3E8" />
            <stop offset="1" stopColor="#DDF3E8" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="130" cy="59" r="54" fill="url(#m2Glow)" className="m2-glow" />
        <path d="M18 40 H 70" stroke="#E4E4DF" strokeWidth="1.2" strokeDasharray="2 4" />
        <path d="M18 78 H 70" stroke="#E4E4DF" strokeWidth="1.2" strokeDasharray="2 4" />
        <path d="M190 40 H 242" stroke="#E4E4DF" strokeWidth="1.2" strokeDasharray="2 4" />
        <path d="M190 78 H 242" stroke="#E4E4DF" strokeWidth="1.2" strokeDasharray="2 4" />
        <g className="m2-f m2-f0">
          <rect x="22" y="35" width="26" height="10" rx="5" fill="#FFFFFF" stroke="#CBCBC3" />
          <circle cx="28" cy="40" r="2" fill="#19C37D" />
        </g>
        <g className="m2-f m2-f1">
          <rect x="212" y="73" width="26" height="10" rx="5" fill="#FFFFFF" stroke="#CBCBC3" />
          <circle cx="218" cy="78" r="2" fill="#19C37D" />
        </g>
        <g className="m2-f m2-f2">
          <rect x="22" y="73" width="26" height="10" rx="5" fill="#FFFFFF" stroke="#CBCBC3" />
          <circle cx="28" cy="78" r="2" fill="#19C37D" />
        </g>
        <circle cx="130" cy="59" r="36" fill="#FFFFFF" stroke="#EFEFEA" strokeWidth="5" />
        <circle
          className="m2-arc"
          cx="130"
          cy="59"
          r="36"
          fill="none"
          stroke="#19C37D"
          strokeWidth="5"
          strokeLinecap="round"
          pathLength={300}
          strokeDasharray="0 300"
          transform="rotate(-90 130 59)"
        />
        <g>
          <rect x="115" y="45" width="30" height="8" rx="4" fill="#E4E4DF" />
          <rect x="115" y="56" width="30" height="8" rx="4" fill="#E4E4DF" />
          <rect x="115" y="67" width="30" height="8" rx="4" fill="#E4E4DF" />
          <rect className="m2-l m2-l0" x="115" y="67" width="30" height="8" rx="4" fill="#19C37D" />
          <rect className="m2-l m2-l1" x="115" y="56" width="30" height="8" rx="4" fill="#19C37D" />
          <rect className="m2-l m2-l2" x="115" y="45" width="30" height="8" rx="4" fill="#0B8A5C" />
        </g>
        <g className="m2-done">
          <circle cx="160" cy="31" r="8" fill="#0B8A5C" />
          <path d="M156.5 31l2.4 2.4 4.6-4.8" fill="none" stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      </svg>
    </div>
  )
}
