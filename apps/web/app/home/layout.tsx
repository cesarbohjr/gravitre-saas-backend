import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Home | Gravitre",
  "Your role-aware Gravitre home — quick actions, intelligence health, and pending approvals.",
  { canonical: "/home" },
)

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  return children
}
