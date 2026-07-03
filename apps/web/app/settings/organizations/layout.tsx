import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Organizations | Gravitre",
  "Manage organization membership and invites.",
  { canonical: "/settings/organizations" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
