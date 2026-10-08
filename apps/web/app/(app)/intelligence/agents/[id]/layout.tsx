import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Agent intelligence | Gravitre",
  "Agent intelligence profile.",
  { canonical: "/intelligence/agents" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
