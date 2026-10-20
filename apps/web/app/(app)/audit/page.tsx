import { redirect } from "next/navigation"

/** Audit trail has moved to Trust & Safety. */
export default function AuditPage() {
  redirect("/trust-safety?tab=audit")
}
