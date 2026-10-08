import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Retired Runs list — Activity hub is canonical. Detail stays at /runs/[id]. */
export default function RunsListRedirectPage() {
  redirect(APP_ROUTES.activity)
}
