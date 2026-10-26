import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Role permissions | Gravitre",
  "What each workspace role can do.",
  { canonical: "/settings/roles" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
