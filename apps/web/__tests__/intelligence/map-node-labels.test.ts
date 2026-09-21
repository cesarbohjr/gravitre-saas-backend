import { describe, expect, it } from "vitest"
import {
  dedupeMapNodesByLabel,
  mapLabelFingerprint,
  truncateMapLabel,
} from "@/lib/intelligence/map-node-labels"

describe("map-node-labels", () => {
  it("truncates long labels on a word boundary", () => {
    const label =
      "OAuth token expiring soon: Connector token expires in 0 hours. HubSpot step refresh"
    const short = truncateMapLabel(label, 42)
    expect(short.length).toBeLessThanOrEqual(42)
    expect(short.endsWith("…")).toBe(true)
    expect(short.includes("HubSpot")).toBe(false)
  })

  it("fingerprints near-duplicate OAuth alerts onto one stem", () => {
    const a =
      "OAuth token expiring soon: Connector token expires in 0 hours. HubSpot step A"
    const b =
      "OAuth token expiring soon: Connector token expires in 0 hours. HubSpot step B"
    expect(mapLabelFingerprint(a)).toBe(mapLabelFingerprint(b))
  })

  it("dedupes signal nodes by fingerprint and caps count", () => {
    const nodes = [
      { id: "1", label: "OAuth token expiring soon: Connector token expires in 0 hours. HubSpot step A", emphasis: 1 },
      { id: "2", label: "OAuth token expiring soon: Connector token expires in 0 hours. HubSpot step B", emphasis: 0.9 },
      { id: "3", label: "Pipeline velocity dropped in outbound", emphasis: 1 },
      { id: "4", label: "Reply rate rising in enterprise segment", emphasis: 0.8 },
    ]
    const deduped = dedupeMapNodesByLabel(nodes, 6)
    expect(deduped).toHaveLength(3)
    expect(deduped[0]?.id).toBe("1")
    expect(deduped.some((n) => n.label.includes("Pipeline"))).toBe(true)
    expect(deduped.some((n) => n.label.includes("Reply"))).toBe(true)
  })
})
