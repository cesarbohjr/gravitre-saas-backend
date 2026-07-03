import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "AI Team | Gravitre",
  "Manage AI agents, profiles, and team capabilities.",
  { canonical: "/agents" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
