import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Onboarding | Gravitre",
  "Complete org onboarding setup.",
  { canonical: "/onboarding" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
