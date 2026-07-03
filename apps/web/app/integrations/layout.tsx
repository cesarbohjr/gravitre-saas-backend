import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Integrations | Gravitre",
  "Integration settings and connections.",
  { canonical: "/integrations" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
