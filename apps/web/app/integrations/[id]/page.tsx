import { redirect } from "next/navigation"

/** Legacy route — connector detail is the customer-facing integration surface. */
export default async function IntegrationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  redirect(`/connectors/${id}`)
}
