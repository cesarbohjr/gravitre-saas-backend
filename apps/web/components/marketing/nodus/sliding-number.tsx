"use client"

/** Simplified stand-in — avoids react-use-measure dependency for Nodus port. */
export function SlidingNumber({
  value,
}: {
  value: number
  padStart?: boolean
  decimalSeparator?: string
}) {
  return <span className="tabular-nums">{value}</span>
}
