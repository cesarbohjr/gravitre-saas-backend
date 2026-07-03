import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Workspace Chat | Gravitre",
  "Multi-turn workspace chat with tools and saved threads.",
  { canonical: "/assistant" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
