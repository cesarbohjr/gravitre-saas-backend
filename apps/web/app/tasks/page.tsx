import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Orphan route — workflow runs live under Runs. */
export default function TasksRedirectPage() {
  redirect(APP_ROUTES.runs)
}
