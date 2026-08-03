import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Orphan route — Activity hub is canonical. */
export default function TasksRedirectPage() {
  redirect(APP_ROUTES.activity)
}
