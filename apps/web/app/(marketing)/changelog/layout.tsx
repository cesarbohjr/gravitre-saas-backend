import { marketingMetadata } from "@/lib/seo"
import { MARKETING_COPY } from "@/lib/marketing-copy"

export const metadata = marketingMetadata({
  title: "Changelog",
  description: "Product updates, new features, improvements, and security releases for the Gravitre platform.",
  ogDescription: MARKETING_COPY.changelog.subtitle,
})

export default function ChangelogLayout({ children }: { children: React.ReactNode }) {
  return children
}
