import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Enterprise | Gravitre",
  "Enterprise branding and controls.",
  { canonical: "/settings/enterprise" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
