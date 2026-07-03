import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Connectors | Gravitre",
  "Connect external systems and integrations.",
  { canonical: "/connectors" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
