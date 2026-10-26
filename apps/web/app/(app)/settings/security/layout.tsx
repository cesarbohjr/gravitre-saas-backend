import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Security | Gravitre",
  "Sign in, single sign on and access controls for this workspace.",
  { canonical: "/settings/security" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
