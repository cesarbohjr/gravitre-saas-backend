import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Home | Gravitre",
  "Your intelligence command surface — learning trends, approvals, and Gravitre AI in one place.",
  { canonical: "/home" },
)

/** Authenticated dashboard — always render fresh (no stale shell with removed callouts). */
export const dynamic = "force-dynamic"

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  return children
}
