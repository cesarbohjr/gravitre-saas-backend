"use client"

import { useEffect, useId, useMemo, useRef, useState } from "react"
import useSWR, { mutate as globalMutate } from "swr"
import { useTheme } from "next-themes"
import {
  BadgeCheck,
  Briefcase,
  Camera,
  Check,
  Clock,
  ImagePlus,
  Loader2,
  MapPin,
  Monitor,
  Moon,
  Save,
  SlidersHorizontal,
  Sun,
  UserRound,
  X,
} from "lucide-react"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { SettingsShell } from "@/components/settings/settings-shell"
import { ProfileSessions } from "@/components/settings/profile-sessions"
import { SetError, SetIco, SetPill, SetSkeleton, SetSwitch, SetTabs } from "@/components/settings/settings-kit"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { authApi, notificationsApi, type NotificationChannelPreference } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { useAccountProfile } from "@/hooks/use-account-profile"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useUserProfile } from "@/lib/user-profile-context"
import {
  applyCompactTables,
  BIO_LIMIT,
  formFromUser,
  initialForm,
  isFormDirty,
  ME_KEY,
  profileApi,
  roleLabel,
  TIME_ZONES,
  timeZoneLabel,
  updateFromForm,
  type AuthMeResponse,
  type ProfileForm,
  type ProfilePreferences,
  type ThemeChoice,
} from "@/lib/settings-api/profile"
import "@/components/settings/profile.css"

const NOTIFICATION_PREFS_KEY = "notification-event-preferences"
const WEEKLY_SUMMARY = "weekly_summary"

export default function ProfilePage() {
  const { user, loading } = useAuth()
  // Drives which sections the settings rail shows; admin-only sections stay hidden for non-admins.
  const { showAdmin, isAdmin } = useOrgAdmin()

  if (loading) {
    return (
      <AppShell title="Settings">
        <SettingsShell activeSection="profile" isAdmin={showAdmin} hideHeader>
          <section className="gs-card">
            <SetSkeleton rows={4} label="Loading profile" />
          </section>
        </SettingsShell>
      </AppShell>
    )
  }

  return (
    <AppShell title="Settings">
      <SettingsShell activeSection="profile" isAdmin={showAdmin} hideHeader>
        {user ? (
          <ProfileContent signedIn isAdmin={isAdmin} />
        ) : (
          <section className="gs-card">
            <div className="gs-empty">
              <b>Sign in required</b>
              <p>Sign in to edit your profile.</p>
            </div>
          </section>
        )}
      </SettingsShell>
    </AppShell>
  )
}

function ProfileContent({ signedIn, isAdmin }: { signedIn: boolean; isAdmin: boolean }) {
  const { profile, updateProfile, setAvatarImage: setContextAvatarImage } = useUserProfile()
  const account = useAccountProfile()
  const hasProfilePhoto = Boolean(account.avatarUrl)
  const { data: me, error: meError, isLoading: meLoading, mutate: mutateMe } = useSWR<AuthMeResponse>(
    signedIn ? ME_KEY : null,
    apiFetcher,
    { revalidateOnFocus: false },
  )
  const serverUser = me?.user
  const saved = useMemo(() => formFromUser(serverUser), [serverUser])
  const [form, setForm] = useState<ProfileForm | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [savedFlash, setSavedFlash] = useState(false)
  const [showAvatarModal, setShowAvatarModal] = useState(false)
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Seed the form once the server profile arrives (and again after each save).
  const seededFor = useRef<string | null>(null)
  useEffect(() => {
    if (!serverUser) return
    const stamp = JSON.stringify(saved)
    if (seededFor.current === stamp) return
    seededFor.current = stamp
    setForm(initialForm(saved, profile))
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seed from the saved server values only
  }, [serverUser, saved])

  const current = form ?? saved
  const dirty = form ? isFormDirty(form, saved) : false
  const setField = (key: keyof ProfileForm, value: string) => {
    setSavedFlash(false)
    setForm((prev) => ({ ...(prev ?? saved), [key]: value }))
  }

  const fullName = `${current.firstName} ${current.lastName}`.trim() || account.displayName
  const email = serverUser?.email || account.email || ""

  const handleSaveProfile = async () => {
    if (!form) return
    setIsSaving(true)
    try {
      await profileApi.update(updateFromForm(form))
      updateProfile({
        firstName: form.firstName.trim(),
        lastName: form.lastName.trim(),
        jobTitle: form.jobTitle.trim(),
        department: form.department.trim(),
        phone: form.phone.trim(),
        location: form.location.trim(),
        timezone: form.timezone.trim(),
        bio: form.bio.trim(),
      })
      await Promise.all([mutateMe(), globalMutate("account-profile-me")])
      setSavedFlash(true)
      toast.success("Profile updated")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update profile")
    } finally {
      setIsSaving(false)
    }
  }

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.currentTarget
    const file = input.files?.[0]
    if (!file) return
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Profile photo must be 5MB or smaller")
      input.value = ""
      return
    }
    try {
      setIsUploadingAvatar(true)
      const response = await authApi.uploadAvatar(file)
      setContextAvatarImage(response.avatar_url)
      await globalMutate("account-profile-me")
      await account.refresh()
      await mutateMe()
      toast.success("Profile photo updated")
      setShowAvatarModal(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to upload profile photo")
    } finally {
      setIsUploadingAvatar(false)
      input.value = ""
    }
  }

  const handleRemoveAvatar = async () => {
    try {
      await authApi.removeAvatar()
      setContextAvatarImage(null)
      await globalMutate("account-profile-me")
      await account.refresh()
      await mutateMe()
      toast.success("Profile photo removed")
      setShowAvatarModal(false)
    } catch {
      toast.error("Failed to remove profile photo")
    }
  }

  if (meError && !me) {
    return (
      <section className="gs-card">
        <SetError message="Could not load your profile." onRetry={() => void mutateMe()} />
      </section>
    )
  }
  if (meLoading && !me) {
    return (
      <section className="gs-card">
        <SetSkeleton rows={4} label="Loading profile" />
      </section>
    )
  }

  const metaLine = [
    current.jobTitle ? { icon: Briefcase, text: current.jobTitle, label: "Job title" } : null,
    current.location ? { icon: MapPin, text: current.location, label: "Location" } : null,
    current.timezone ? { icon: Clock, text: timeZoneLabel(current.timezone), label: "Time zone" } : null,
  ].filter(Boolean) as { icon: typeof Briefcase; text: string; label: string }[]

  return (
    <>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleAvatarUpload}
        accept="image/jpeg,image/png,image/gif,image/webp"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        disabled={isUploadingAvatar}
      />
      <Dialog open={showAvatarModal} onOpenChange={setShowAvatarModal}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{hasProfilePhoto ? "Change photo" : "Add photo"}</DialogTitle>
            <DialogDescription>Your photo appears in Chat, the header menu, and team member lists.</DialogDescription>
          </DialogHeader>
          <div className="flex justify-center">
            <UserAccountAvatar useCurrentUser className="h-28 w-28 text-3xl" fallbackClassName="text-3xl" />
          </div>
          <button
            type="button"
            disabled={isUploadingAvatar}
            onClick={() => {
              if (isUploadingAvatar) return
              fileInputRef.current?.click()
            }}
            className="flex w-full items-center gap-3 rounded-[10px] border border-divide bg-[color:var(--g-surface-2)] p-4 text-left transition-colors hover:bg-secondary/50 disabled:opacity-60"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <ImagePlus className="h-5 w-5 text-primary" aria-hidden />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">{isUploadingAvatar ? "Uploading…" : "Upload photo"}</p>
              <p className="text-xs text-muted-foreground">JPG, PNG, GIF, or WebP, max 5MB</p>
            </div>
          </button>
          {hasProfilePhoto ? (
            <button
              type="button"
              onClick={() => void handleRemoveAvatar()}
              className="flex w-full items-center gap-3 rounded-[10px] border border-destructive/20 bg-destructive/5 p-4 text-left transition-colors hover:bg-destructive/10"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-destructive/10">
                <X className="h-5 w-5 text-destructive" aria-hidden />
              </div>
              <div>
                <p className="text-sm font-medium text-destructive">Remove photo</p>
                <p className="text-xs text-muted-foreground">Revert to initials</p>
              </div>
            </button>
          ) : null}
        </DialogContent>
      </Dialog>

      <section className="gs-card profile-hero" aria-label="Your profile">
        <div className="profile-banner" aria-hidden>
          <svg width="100%" height="96" preserveAspectRatio="none" viewBox="0 0 1400 96">
            <g className="gs-drift" fill="none">
              <path d="M0 70 C 200 20, 400 110, 700 50 S 1100 30, 1400 70" strokeOpacity=".25" />
              <path d="M0 84 C 220 40, 420 120, 720 64 S 1120 44, 1400 84" strokeOpacity=".15" />
            </g>
          </svg>
        </div>
        <div className="profile-id">
          <div className="profile-avatar">
            <div className="profile-avatar-ring">
              <UserAccountAvatar useCurrentUser className="h-full w-full text-[34px]" fallbackClassName="text-[34px] font-semibold" />
            </div>
            <button
              type="button"
              className="gs-btn line sm profile-photo-btn"
              aria-label={hasProfilePhoto ? "Change photo" : "Add photo"}
              onClick={() => setShowAvatarModal(true)}
            >
              <Camera size={16} aria-hidden />
            </button>
          </div>
          <div className="profile-who">
            <div className="profile-name-row">
              <h2>{fullName}</h2>
              {serverUser?.email_confirmed ? (
                <SetPill tone="green">
                  <BadgeCheck size={13} aria-hidden />
                  Verified
                </SetPill>
              ) : null}
            </div>
            {metaLine.length > 0 ? (
              <div className="profile-meta">
                {metaLine.map((item) => (
                  <span key={item.label}>
                    <item.icon size={15} aria-hidden />
                    <span className="sr-only">{item.label}: </span>
                    {item.text}
                  </span>
                ))}
              </div>
            ) : (
              <div className="profile-meta">
                <span>Add your job title, location and time zone below.</span>
              </div>
            )}
          </div>
          <div className="profile-save">
            <span role="status" aria-live="polite">
              {dirty ? (
                <span className="profile-dirty">Unsaved changes</span>
              ) : savedFlash ? (
                <span className="profile-saved">
                  <Check size={14} aria-hidden />
                  Saved
                </span>
              ) : null}
            </span>
            <button
              type="button"
              className="gs-btn dark"
              onClick={() => void handleSaveProfile()}
              disabled={isSaving || !dirty}
            >
              {isSaving ? <Loader2 size={16} className="animate-spin" aria-hidden /> : <Save size={16} aria-hidden />}
              {isSaving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </div>
      </section>

      <div className="profile-cols">
        <div className="profile-col-main">
          <section className="gs-card pad" aria-labelledby="profile-personal">
            <div className="profile-card-title">
              <SetIco icon={UserRound} />
              <div>
                <h3 id="profile-personal">Personal information</h3>
                <div className="gs-sub">How you appear to teammates and agents</div>
              </div>
            </div>
            <div className="gs-grid-fields">
              <Field label="First name" value={current.firstName} onChange={(v) => setField("firstName", v)} autoComplete="given-name" />
              <Field label="Last name" value={current.lastName} onChange={(v) => setField("lastName", v)} autoComplete="family-name" />
              <Field
                label="Email address"
                type="email"
                value={email}
                readOnly
                hint="Your sign in email. It can't be changed here."
              />
              <Field label="Phone number" type="tel" value={current.phone} onChange={(v) => setField("phone", v)} autoComplete="tel" maxLength={40} />
              <Field label="Job title" value={current.jobTitle} onChange={(v) => setField("jobTitle", v)} autoComplete="organization-title" />
              <Field label="Department" value={current.department} onChange={(v) => setField("department", v)} />
              <Field label="Location" value={current.location} onChange={(v) => setField("location", v)} placeholder="City, region" maxLength={120} />
              <TimeZoneField value={current.timezone} onChange={(v) => setField("timezone", v)} />
            </div>
            <BioField value={current.bio} onChange={(v) => setField("bio", v)} />
          </section>

          <ProfilePreferencesCard me={me} onSaved={() => void mutateMe()} />
        </div>

        <div className="profile-col-side">
          <section className="gs-card pad" aria-labelledby="profile-identity">
            <h3 id="profile-identity" style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
              Your identity
            </h3>
            <p className="gs-sub" style={{ margin: "8px 0 0", fontSize: 14, lineHeight: 1.55, color: "var(--gs-ink-3)" }}>
              Your name and photo identify you across the workspace. Access and permissions come from your workspace role.
            </p>
            <IdentityChips me={me} isAdmin={isAdmin} />
          </section>

          <ProfileSessions enabled={signedIn} />

          <PasswordCard />
        </div>
      </div>
    </>
  )
}

function IdentityChips({ me, isAdmin }: { me: AuthMeResponse | undefined; isAdmin: boolean }) {
  const currentOrgId = me?.org_id ?? me?.current_org?.id ?? null
  const membershipRole = me?.organizations?.find((org) => org.id === currentOrgId)?.role ?? me?.role
  const chips = [
    roleLabel(membershipRole),
    isAdmin ? "Admin view" : null,
    me?.platformAdmin ? "Platform admin" : null,
  ].filter(Boolean) as string[]
  if (chips.length === 0) {
    return <p className="gs-sub" style={{ marginTop: 14 }}>Your workspace role is not available right now.</p>
  }
  return (
    <div className="profile-chips">
      {chips.map((chip) => (
        <span key={chip} className="gs-chip">
          {chip}
        </span>
      ))}
    </div>
  )
}

function ProfilePreferencesCard({ me, onSaved }: { me: AuthMeResponse | undefined; onSaved: () => void }) {
  const { resolvedTheme, setTheme } = useTheme()
  const prefs: ProfilePreferences = {
    theme: me?.user?.preferences?.theme ?? null,
    compact_tables: Boolean(me?.user?.preferences?.compact_tables),
  }
  const [pendingTheme, setPendingTheme] = useState<ThemeChoice | null>(null)
  const [compact, setCompact] = useState<boolean | null>(null)
  const theme: ThemeChoice =
    pendingTheme ?? (prefs.theme === "system" ? "system" : resolvedTheme === "dark" ? "dark" : "light")
  const compactOn = compact ?? prefs.compact_tables

  const {
    data: notif,
    error: notifError,
    isLoading: notifLoading,
    mutate: mutateNotif,
  } = useSWR<{ preferences: Record<string, NotificationChannelPreference> }>(NOTIFICATION_PREFS_KEY, () =>
    notificationsApi.getPreferences(),
  )
  const [digestSaving, setDigestSaving] = useState(false)
  const digest = Boolean(notif?.preferences?.[WEEKLY_SUMMARY]?.email_enabled)

  const savePreference = async (update: Partial<ProfilePreferences>) => {
    await profileApi.update({ preferences: update })
    onSaved()
  }

  const pickTheme = async (next: ThemeChoice) => {
    const previous = theme
    setPendingTheme(next)
    if (next !== "system") setTheme(next)
    else if (typeof window !== "undefined" && window.matchMedia) {
      setTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    }
    try {
      await savePreference({ theme: next })
    } catch (err) {
      setPendingTheme(null)
      if (previous !== "system") setTheme(previous)
      toast.error(err instanceof Error ? err.message : "Could not save your theme")
      return
    }
    setPendingTheme(null)
  }

  const toggleCompact = async (next: boolean) => {
    setCompact(next)
    applyCompactTables(next)
    try {
      await savePreference({ compact_tables: next })
    } catch (err) {
      setCompact(!next)
      applyCompactTables(!next)
      toast.error(err instanceof Error ? err.message : "Could not save Compact tables")
      return
    }
    setCompact(null)
  }

  const toggleDigest = async (next: boolean) => {
    setDigestSaving(true)
    const optimistic = {
      preferences: {
        ...(notif?.preferences ?? {}),
        [WEEKLY_SUMMARY]: { bell_enabled: true, ...(notif?.preferences?.[WEEKLY_SUMMARY] ?? {}), email_enabled: next },
      },
    }
    try {
      await mutateNotif(
        async () => {
          const result = await notificationsApi.updatePreferences({ [WEEKLY_SUMMARY]: { email_enabled: next } })
          return result.preferences ? { preferences: result.preferences } : optimistic
        },
        { optimisticData: optimistic, rollbackOnError: true, revalidate: false },
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update the weekly digest")
    } finally {
      setDigestSaving(false)
    }
  }

  return (
    <section className="gs-card pad" aria-labelledby="profile-preferences">
      <div className="profile-card-title" style={{ marginBottom: 14 }}>
        <SetIco icon={SlidersHorizontal} tone="mute" />
        <div>
          <h3 id="profile-preferences">Preferences</h3>
          <div className="gs-sub">Only affects how Gravitre looks for you</div>
        </div>
      </div>
      <div className="profile-pref">
        <div>
          <b>Theme</b>
          <span className="gs-sub">Match your system or pick one</span>
        </div>
        <SetTabs<ThemeChoice>
          label="Theme"
          value={theme}
          onChange={(next) => void pickTheme(next)}
          options={[
            { id: "light", label: "Light", icon: Sun },
            { id: "dark", label: "Dark", icon: Moon },
            { id: "system", label: "System", icon: Monitor },
          ]}
        />
      </div>
      <div className="profile-pref">
        <div>
          <b>Weekly digest email</b>
          <span className="gs-sub">
            {notifError ? "Could not load your notification settings." : "A Monday summary of what your agents did"}
          </span>
        </div>
        {notifError ? (
          <button type="button" className="gs-btn line sm" onClick={() => void mutateNotif()}>
            Try again
          </button>
        ) : (
          <SetSwitch
            label="Weekly digest email"
            checked={digest}
            disabled={digestSaving || (notifLoading && !notif)}
            onChange={(next) => void toggleDigest(next)}
          />
        )}
      </div>
      <div className="profile-pref">
        <div>
          <b>Compact tables</b>
          <span className="gs-sub">Fit more rows on screen</span>
        </div>
        <SetSwitch label="Compact tables" checked={compactOn} disabled={!me} onChange={(next) => void toggleCompact(next)} />
      </div>
    </section>
  )
}

function PasswordCard() {
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isChangingPassword, setIsChangingPassword] = useState(false)

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword) {
      toast.error("Current and new password are required")
      return
    }
    if (newPassword.length < 8) {
      toast.error("New password must be at least 8 characters")
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error("New passwords do not match")
      return
    }
    setIsChangingPassword(true)
    try {
      await authApi.changePassword(currentPassword, newPassword)
      toast.success("Password changed")
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to change password")
    } finally {
      setIsChangingPassword(false)
    }
  }

  return (
    <section className="gs-card pad" aria-labelledby="profile-password">
      <h3 id="profile-password" style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
        Password
      </h3>
      <p className="gs-sub" style={{ marginTop: 6 }}>
        Use at least 8 characters.
      </p>
      <form
        className="profile-password"
        onSubmit={(event) => {
          event.preventDefault()
          void handleChangePassword()
        }}
      >
        <Field label="Current password" type="password" value={currentPassword} onChange={setCurrentPassword} autoComplete="current-password" />
        <Field label="New password" type="password" value={newPassword} onChange={setNewPassword} autoComplete="new-password" />
        <Field label="Confirm new password" type="password" value={confirmPassword} onChange={setConfirmPassword} autoComplete="new-password" />
        <div>
          <button type="submit" className="gs-btn line sm" disabled={isChangingPassword}>
            {isChangingPassword ? <Loader2 size={14} className="animate-spin" aria-hidden /> : null}
            Change password
          </button>
        </div>
      </form>
    </section>
  )
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  readOnly,
  hint,
  placeholder,
  autoComplete,
  maxLength,
}: {
  label: string
  value: string
  onChange?: (value: string) => void
  type?: string
  readOnly?: boolean
  hint?: string
  placeholder?: string
  autoComplete?: string
  maxLength?: number
}) {
  const id = useId()
  return (
    <div className="gs-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        readOnly={readOnly}
        aria-readonly={readOnly || undefined}
        aria-describedby={hint ? `${id}-hint` : undefined}
        placeholder={placeholder}
        autoComplete={autoComplete}
        maxLength={maxLength}
        onChange={(event) => onChange?.(event.target.value)}
        style={readOnly ? { background: "var(--gs-tile)", color: "var(--gs-ink-3)" } : undefined}
      />
      {hint ? (
        <span id={`${id}-hint`} className="hint">
          {hint}
        </span>
      ) : null}
    </div>
  )
}

function TimeZoneField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const id = useId()
  const known = TIME_ZONES.some((zone) => zone.value === value)
  return (
    <div className="gs-field">
      <label htmlFor={id}>Time zone</label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Not set</option>
        {TIME_ZONES.map((zone) => (
          <option key={zone.value} value={zone.value}>
            {zone.label}
          </option>
        ))}
        {value && !known ? <option value={value}>{timeZoneLabel(value)}</option> : null}
      </select>
    </div>
  )
}

function BioField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const id = useId()
  return (
    <div className="gs-field profile-bio">
      <label htmlFor={id}>About you</label>
      <textarea
        id={id}
        value={value}
        maxLength={BIO_LIMIT}
        onChange={(event) => onChange(event.target.value)}
        placeholder="A line or two your teammates will see"
        aria-describedby={`${id}-count`}
      />
      <span id={`${id}-count`} className="profile-bio-count">
        {value.length}/{BIO_LIMIT}
      </span>
    </div>
  )
}
