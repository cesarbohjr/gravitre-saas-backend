/**
 * Profile page data: GET/PATCH /api/auth/me (name, title, department on
 * public.users; phone, location, time zone, bio and preferences on the auth
 * user's metadata) and GET /api/auth/sessions.
 */
import { apiFetch } from "@/lib/fetcher"
import { extractApiErrorMessage } from "@/lib/api-error-message"

export type ThemeChoice = "light" | "dark" | "system"

export interface ProfilePreferences {
  theme: ThemeChoice | null
  compact_tables: boolean
}

export interface ProfileUser {
  id: string
  email?: string | null
  full_name?: string | null
  avatar_url?: string | null
  job_title?: string | null
  department?: string | null
  role?: string | null
  phone?: string | null
  location?: string | null
  timezone?: string | null
  bio?: string | null
  preferences?: ProfilePreferences | null
  /** null/undefined when the server could not read the auth user. */
  email_confirmed?: boolean | null
}

export interface AuthMeResponse {
  user_id?: string
  org_id?: string | null
  role?: string | null
  platformAdmin?: boolean
  user?: ProfileUser
  organizations?: Array<{ id: string; name?: string | null; role?: string | null }>
  current_org?: { id: string; name?: string | null } | null
}

export interface ProfileUpdate {
  full_name?: string
  job_title?: string
  department?: string
  phone?: string
  location?: string
  timezone?: string
  bio?: string
  preferences?: Partial<ProfilePreferences>
}

export interface AuthSession {
  id: string
  device: string
  user_agent?: string | null
  ip: string
  created_at?: string | null
  last_active: string
  current: boolean
}

export const ME_KEY = "/api/auth/me"
export const SESSIONS_KEY = "/api/auth/sessions"
export const BIO_LIMIT = 280

async function patchJson<T>(url: string, body: unknown): Promise<T> {
  const response = await apiFetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(extractApiErrorMessage(payload) ?? `Request failed: ${response.status}`)
  }
  return payload as T
}

export const profileApi = {
  update: (data: ProfileUpdate) => patchJson<ProfileUser>(ME_KEY, data),
}

/** Fields the Personal information form edits. Email is the sign in identity and read only. */
export interface ProfileForm {
  firstName: string
  lastName: string
  phone: string
  jobTitle: string
  department: string
  location: string
  timezone: string
  bio: string
}

export const EMPTY_PROFILE_FORM: ProfileForm = {
  firstName: "",
  lastName: "",
  phone: "",
  jobTitle: "",
  department: "",
  location: "",
  timezone: "",
  bio: "",
}

export function splitName(fullName: string | null | undefined): { firstName: string; lastName: string } {
  const [firstName = "", ...rest] = String(fullName ?? "").trim().split(/\s+/).filter(Boolean)
  return { firstName, lastName: rest.join(" ") }
}

/** What the server has saved, as form values. */
export function formFromUser(user: ProfileUser | null | undefined): ProfileForm {
  if (!user) return { ...EMPTY_PROFILE_FORM }
  return {
    ...splitName(user.full_name),
    phone: user.phone ?? "",
    jobTitle: user.job_title ?? "",
    department: user.department ?? "",
    location: user.location ?? "",
    timezone: user.timezone ?? "",
    bio: user.bio ?? "",
  }
}

/**
 * Starting values: the server's, plus any phone, location, time zone or bio
 * that only ever lived in this browser (before they were saved server side),
 * so the person can save them now. Those show as unsaved changes.
 */
export function initialForm(
  saved: ProfileForm,
  local: Partial<Record<"phone" | "location" | "timezone" | "bio", string>> | null | undefined,
): ProfileForm {
  const next = { ...saved }
  for (const key of ["phone", "location", "timezone", "bio"] as const) {
    const value = String(local?.[key] ?? "").trim()
    if (!next[key] && value) next[key] = key === "bio" ? value.slice(0, BIO_LIMIT) : value
  }
  return next
}

export function isFormDirty(form: ProfileForm, saved: ProfileForm): boolean {
  return (Object.keys(saved) as (keyof ProfileForm)[]).some((key) => form[key].trim() !== saved[key].trim())
}

export function updateFromForm(form: ProfileForm): ProfileUpdate {
  return {
    full_name: `${form.firstName.trim()} ${form.lastName.trim()}`.trim(),
    job_title: form.jobTitle.trim(),
    department: form.department.trim(),
    phone: form.phone.trim(),
    location: form.location.trim(),
    timezone: form.timezone.trim(),
    bio: form.bio.trim(),
  }
}

export const TIME_ZONES: { value: string; label: string }[] = [
  { value: "America/Los_Angeles", label: "Pacific Time" },
  { value: "America/Denver", label: "Mountain Time" },
  { value: "America/Chicago", label: "Central Time" },
  { value: "America/New_York", label: "Eastern Time" },
  { value: "UTC", label: "UTC" },
  { value: "Europe/London", label: "UK Time" },
  { value: "Europe/Paris", label: "Central European Time" },
  { value: "Asia/Tokyo", label: "Japan Time" },
]

export function timeZoneLabel(value: string | null | undefined): string | null {
  if (!value) return null
  return TIME_ZONES.find((zone) => zone.value === value)?.label ?? value.replace(/_/g, " ")
}

/** Browser and OS from a user agent: "Chrome on macOS". */
export function describeUserAgent(userAgent: string | null | undefined): string {
  const ua = String(userAgent ?? "")
  if (!ua.trim()) return "Unknown device"
  const browser = /Edg(e|A|iOS)?\//.test(ua)
    ? "Edge"
    : /OPR\/|Opera/.test(ua)
      ? "Opera"
      : /Firefox\/|FxiOS\//.test(ua)
        ? "Firefox"
        : /Chrome\/|CriOS\//.test(ua)
          ? "Chrome"
          : /Safari\//.test(ua)
            ? "Safari"
            : null
  const os = /iPhone|iPad|iPod/.test(ua)
    ? "iOS"
    : /Android/.test(ua)
      ? "Android"
      : /CrOS/.test(ua)
        ? "ChromeOS"
        : /Windows/.test(ua)
          ? "Windows"
          : /Mac OS X|Macintosh/.test(ua)
            ? "macOS"
            : /Linux/.test(ua)
              ? "Linux"
              : null
  if (browser && os) return `${browser} on ${os}`
  if (browser) return browser
  if (os) return `Browser on ${os}`
  return "Unknown device"
}

/** Applies the Compact tables preference (settings-kit.css reacts to it). */
export function applyCompactTables(on: boolean) {
  if (typeof document === "undefined") return
  if (on) document.documentElement.dataset.compactTables = "true"
  else delete document.documentElement.dataset.compactTables
}

export function roleLabel(role: string | null | undefined): string | null {
  const value = String(role ?? "").trim().toLowerCase()
  if (!value) return null
  return value.charAt(0).toUpperCase() + value.slice(1)
}
