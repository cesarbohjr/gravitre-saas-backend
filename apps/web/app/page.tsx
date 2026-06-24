import { redirect } from "next/navigation"

import { oauthStateProvider } from "@/lib/clickup-oauth-callback"
import { backendBaseUrl } from "@/lib/public-urls"

import MarketingLayout from "./(marketing)/layout"
import MarketingHomePage from "./(marketing)/page"

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
