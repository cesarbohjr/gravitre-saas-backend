import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Human-in-the-loop | Gravitre",
  "Configure who needs approval for read, write, and delete actions by org, department, or user.",
  { canonical: "/settings/approvals" },
)

export default function HitlApprovalsLayout({ children }: { children: React.ReactNode }) {
  return children
}
