import { notFound } from "next/navigation"

import ActivityPage from "@/app/activity/page"

/**
 * Renders one real product surface for screenshot capture. Add a view here
 * rather than reimplementing a surface, so captures cannot drift from the
 * shipping UI.
 */
const VIEWS: Record<string, React.ComponentType> = {
  activity: ActivityPage,
}

export default async function ShotView({
  params,
}: {
  params: Promise<{ view: string }>
}) {
  const { view } = await params
  const Surface = VIEWS[view]
  if (!Surface) notFound()
  return <Surface />
}
