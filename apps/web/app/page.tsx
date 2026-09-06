import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { oauthStateProvider } from "@/lib/clickup-oauth-callback"
import { backendBaseUrl } from "@/lib/public-urls"

import MarketingLayout from "./(marketing)/layout"
import MarketingHomePage from "./(marketing)/page"

export const metadata: Metadata = {
  title: "Gravitre — One AI brain for your entire business",
  description:
    "Connect your tools, teams, and data. Run Gravitre AI, agents, and workflows with live connector checks, human approvals, and learning from verified outcomes.",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Gravitre",
    title: "Gravitre — One AI brain for your entire business",
    description:
      "One shared intelligence across agents, workflows, connectors, and approvals — governed execution, not another AI silo.",
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre — One AI brain for your business" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Gravitre — One AI brain for your entire business",
    description: "Connect your stack. Coordinate the work. Measure whether it worked.",
    images: ["/og-get-started.png"],
  },
}

type RootPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>
}

export default async function RootPage({ searchParams }: RootPageProps) {
  const params = (await searchParams) ?? {}
  const code = typeof params.code === "string" ? params.code : undefined
  const state = typeof params.state === "string" ? params.state : undefined
  if (code && state && oauthStateProvider(state) === "clickup") {
    const target = new URL(`${backendBaseUrl()}/api/connectors/oauth/clickup/callback`)
    target.searchParams.set("code", code)
    target.searchParams.set("state", state)
    redirect(target.toString())
  }

  return (
    <MarketingLayout>
      <MarketingHomePage />
    </MarketingLayout>
  )
}
