import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Settings | Gravitre",
  "Workspace, team, security, and AI settings.",
  { canonical: "/settings" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
