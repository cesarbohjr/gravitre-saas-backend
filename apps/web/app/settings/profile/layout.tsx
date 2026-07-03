import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Profile | Gravitre",
  "Your account profile and preferences.",
  { canonical: "/settings/profile" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
