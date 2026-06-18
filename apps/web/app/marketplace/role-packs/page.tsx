import { redirect } from "next/navigation"

/** Legacy route — unified catalog lives at /marketplace/assets (MKT-6). */
export default function RolePacksPage() {
  redirect("/marketplace/assets?type=department_pack")
}
