import { marketingMetadata } from "@/lib/seo"
import { MARKETING_COPY } from "@/lib/marketing-copy"

export const metadata = marketingMetadata({
  canonical: "/changelog",
  title: "Changelog",
  description: "Read Gravitre product updates, security fixes, and new capabilities across agents, workflows, integrations, approvals, and business intelligence.",
  ogDescription: MARKETING_COPY.changelog.subtitle,
})

export default function ChangelogLayout({ children }: { children: React.ReactNode }) {
  return children
}
