"use client"

import useSWR from "swr"
import { fetcher } from "@/lib/fetcher"

type Prospect = {
  id: string
  full_name: string | null
  role_title: string | null
  email: string | null
  email_status: string
  crm_status: string
  verification_provider: string | null
}
type Response = { items: Prospect[]; crmWriteEnabled: boolean; outreachEnabled: boolean }

export function ProspectingReviewQueue() {
  const { data, error, isLoading } = useSWR<Response>(
    "/api/plays/qualified-prospecting/reviews", fetcher
  )
  return (
    <section className="rounded-[12px] border border-divide bg-[color:var(--g-surface-1)] p-4" aria-label="Prospect review queue">
      <h2 className="text-[15px] font-semibold">Prospects awaiting review</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Verification is not marketing consent. CRM import and email sending stay disabled.
      </p>
      {isLoading && <p className="mt-4 text-sm">Loading saved prospects…</p>}
      {error && <p role="alert" className="mt-4 text-sm text-destructive">Could not load review records.</p>}
      {data && data.items.length === 0 && <p className="mt-4 text-sm text-muted-foreground">No saved prospects yet. Connect sources and run approved discovery.</p>}
      {data && data.items.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead><tr className="border-b border-divide"><th className="p-2">Contact</th><th className="p-2">Email</th><th className="p-2">Validation</th><th className="p-2">Review</th></tr></thead>
            <tbody>{data.items.map(item => (
              <tr className="border-b border-divide" key={item.id}>
                <td className="p-2">{item.full_name || "Identity pending"}<div className="text-muted-foreground">{item.role_title || "Role pending"}</div></td>
                <td className="p-2">{item.email || "Unavailable"}</td>
                <td className="p-2">{item.email_status}</td>
                <td className="p-2">{item.crm_status}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </section>
  )
}
