import { marketingMetadata } from "@/lib/seo"

export const metadata = marketingMetadata({
  title: "Careers at Gravitre AI Operations",
  canonical: "/careers",
  description: "Learn about working at Gravitre, our approach to building AI operations software, and opportunities to join the team.",
})

export default function CareersLayout({ children }: { children: React.ReactNode }) {
  return children
}
