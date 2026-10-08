import { ImageResponse } from "next/og"
import { marketplaceSlugToTitle } from "@/lib/marketplace-metadata"

export const runtime = "edge"
export const alt = "Gravitre Marketplace asset"
export const size = { width: 1200, height: 630 }
export const contentType = "image/png"

type Props = { params: Promise<{ slug: string }> }

export default async function Image({ params }: Props) {
  const { slug } = await params
  const title = marketplaceSlugToTitle(slug)

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "linear-gradient(135deg, #0f172a 0%, #1e293b 45%, #334155 100%)",
          color: "white",
          padding: "64px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              background: "rgba(255,255,255,0.12)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
            }}
          >
            ◆
          </div>
          <span style={{ fontSize: 28, opacity: 0.85 }}>Gravitre Marketplace</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 56, fontWeight: 700, lineHeight: 1.1, maxWidth: 900 }}>{title}</div>
          <div style={{ fontSize: 28, opacity: 0.75 }}>
            Agents, workflows, and knowledge — install with connector checklist
          </div>
        </div>
      </div>
    ),
    { ...size },
  )
}
