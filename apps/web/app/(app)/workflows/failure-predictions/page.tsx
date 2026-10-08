import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Failure Alerts live under Activity → Failures tab. */
export default function FailurePredictionsRedirectPage() {
  redirect(`${APP_ROUTES.activity}?tab=failures`)
}
