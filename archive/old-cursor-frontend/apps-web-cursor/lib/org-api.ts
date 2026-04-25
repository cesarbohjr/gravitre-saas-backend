/**
 * RB-00: Org membership helpers. Same-origin; never log token.
 */

import { getEnvironmentHeader } from "@/lib/environment";

const API = "/api/org";

export type OrgMember = {
  id: string;
  user_id: string;
  role: "admin" | "member";
  created_at: string;
};

function headers(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "X-Environment": getEnvironmentHeader(),
  };
}

export async function fetchOrgMembers(token: string): Promise<{ members: OrgMember[] }> {
  const res = await fetch(`${API}/members`, { headers: headers(token), cache: "no-store" });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data;
}
