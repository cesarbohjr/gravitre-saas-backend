import type { Metadata } from "next"
import { GoogleTagManager } from "@/components/marketing/google-tag-manager"
import { MarketingConsentBanner } from "@/components/marketing/marketing-consent-banner"
import { MarketingChrome } from "@/components/marketing/marketing-chrome"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { getMarketingVisitorCountry } from "@/lib/marketing-geo"

export const metadata: Metadata = {
  title: {
    default: MARKETING_COPY.meta.title,
    template: "%s · Gravitre",
  },
  description: MARKETING_COPY.meta.description,
  keywords: [...MARKETING_COPY.meta.keywords],
  openGraph: {
    type: "website",
    siteName: "Gravitre",
    title: MARKETING_COPY.meta.title,
    description: MARKETING_COPY.meta.description,
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre — AI Operations Platform" }],
  },
  twitter: {
    card: "summary_large_image",
    title: MARKETING_COPY.meta.title,
    description: MARKETING_COPY.meta.description,
    images: ["/og-get-started.png"],
  },
}

export default async function MarketingLayout({ children }: { children: React.ReactNode }) {
  const country = await getMarketingVisitorCountry()

  return (
    <>
      <GoogleTagManager />
      <MarketingChrome>{children}</MarketingChrome>
      <MarketingConsentBanner country={country} />
    </>
  )
}
