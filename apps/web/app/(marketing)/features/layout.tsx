import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Features",
  description:
    "Explore Gravitre's features: agent orchestration, workflow automation, run monitoring, approvals, governance, federation, and a marketplace of role-ready AI agents.",
  ogDescription:
    "Agent orchestration, workflow automation, run monitoring, approvals, governance, and a marketplace of role-ready AI agents.",
})

export default function FeaturesLayout({ children }: { children: React.ReactNode }) {
  return children
}
