import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { oauthStateProvider } from "@/lib/clickup-oauth-callback"
import { backendBaseUrl } from "@/lib/public-urls"

import MarketingLayout from "./(marketing)/layout"
import MarketingHomePage from "./(marketing)/page"

export const metadata: Metadata = {
  title: "Gravitre — Your AI Team, Managed Simply",
  description:
    "Gravitre is the AI operations platform for managing agents, workflows, runs, and approvals — with enterprise-grade governance, federation, and a marketplace of role-ready agents.",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Gravitre",
    title: "Gravitre — Your AI Team, Managed Simply",
    description:
      "Manage AI agents, workflows, runs, and approvals with enterprise-grade governance and a marketplace of role-ready agents.",
    images: [{ url: "/og-get-started.png", width: 1200, height: 630, alt: "Gravitre — AI Operations Platform" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Gravitre — Your AI Team, Managed Simply",
    description: "The AI operations platform for the enterprise.",
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
