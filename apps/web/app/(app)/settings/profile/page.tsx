"use client"

import { useState, useEffect, useRef, useId } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { 
  Save,
  Check,
  Loader2,
  ArrowLeft,
  User,
  Mail,
  Phone,
  Building2,
  MapPin,
    Shield,
  Clock,
  Activity,
  Camera,
  X,
  ImagePlus
} from "lucide-react"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { useUserProfile } from "@/lib/user-profile-context"
import { useAuth } from "@/lib/auth-context"
import { useAccountProfile } from "@/hooks/use-account-profile"
import { authApi } from "@/lib/api"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { toast } from "sonner"
import { mutate as globalMutate } from "swr"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { SettingsShell } from "@/components/settings/settings-shell"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { TYPE } from "@/lib/design-system"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface AuthSession {
  id: string
  device: string
  ip: string
  last_active: string
  current: boolean
}

interface AuthSessionsResponse {
  sessions: AuthSession[]
}

export default function ProfilePage() {
  const { user, loading } = useAuth()
  // Drives which tiers the settings rail shows; admin-only sections stay hidden
  // for non-admins.
  const { showAdmin } = useOrgAdmin()
  const { profile, updateProfile, setAvatarImage: setContextAvatarImage } = useUserProfile()
  const account = useAccountProfile()
  const hasProfilePhoto = Boolean(account.avatarUrl)
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [activeField, setActiveField] = useState<string | null>(null)
  const [showAvatarModal, setShowAvatarModal] = useState(false)
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false)
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [isRevokingAll, setIsRevokingAll] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: sessionsData, error: sessionsError, isLoading: sessionsLoading, mutate: mutateSessions } = useSWR<AuthSessionsResponse>(
    user ? "/api/auth/sessions" : null,
    apiFetcher
  )

  useEffect(() => {
    if (!user) return
    const fullName = String(user.user_metadata?.full_name ?? "").trim()
    const [firstName, ...rest] = fullName.split(" ").filter(Boolean)
    const lastName = rest.join(" ")
    updateProfile({
      firstName: firstName || profile.firstName,
      lastName: lastName || profile.lastName,
      email: user.email ?? profile.email,
    })
  }, [user])

  const handleSaveProfile = async () => {
    setIsSaving(true)
    try {
      const fullName = `${profile.firstName} ${profile.lastName}`.trim()
      await authApi.updateProfile({
        full_name: fullName || undefined,
        job_title: profile.jobTitle.trim() || undefined,
        department: profile.department.trim() || undefined,
      })
      await globalMutate("account-profile-me")
      await globalMutate("/api/auth/me")
      setSaved(true)
      toast.success("Profile updated")
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      console.error("[v0] Update failed:", err)
      toast.error("Failed to update profile")
    } finally {
      setIsSaving(false)
    }
  }

  const handleChange = (field: string, value: string) => {
    updateProfile({ [field]: value })
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
      toast.success("Profile photo updated")
      setShowAvatarModal(false)
    } catch (err) {
      console.error("[v0] Avatar upload failed:", err)
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
      toast.success("Profile photo removed")
      setShowAvatarModal(false)
    } catch (err) {
      console.error("[v0] Avatar remove failed:", err)
      toast.error("Failed to remove profile photo")
    }
  }

  const handleChangePassword = async () => {
    if (!currentPassword || !newPassword) {
      toast.error("Current and new password are required")
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
      console.error("[v0] Password change failed:", err)
      toast.error("Failed to change password")
    } finally {
      setIsChangingPassword(false)
    }
  }

  const handleRevokeSession = async (sessionId: string) => {
    try {
      await authApi.revokeSession(sessionId)
      toast.success("Session revoked")
      await mutateSessions()
    } catch (err) {
      console.error("[v0] Revoke failed:", err)
      toast.error("Failed to revoke session")
    }
  }

  const handleRevokeAllSessions = async () => {
    if (!window.confirm("Revoke all other sessions?")) return
    setIsRevokingAll(true)
    try {
      await authApi.revokeAllSessions()
      toast.success("All sessions revoked")
      await mutateSessions()
    } catch (err) {
      console.error("[v0] Revoke all failed:", err)
      toast.error("Failed to revoke all sessions")
    } finally {
      setIsRevokingAll(false)
    }
  }

  if (loading) {
    return (
      <AppShell title="Settings">
        <SettingsShell activeSection="profile" isAdmin={showAdmin} hideHeader>
          <CenteredLoader fill="parent" label="Loading profile" />
        </SettingsShell>
      </AppShell>
    )
  }

  return (
    <AppShell title="Settings">
      <SettingsShell activeSection="profile" isAdmin={showAdmin} hideHeader>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleAvatarUpload}
          accept="image/jpeg,image/png,image/gif,image/webp"
          className="sr-only"
          tabIndex={-1}
          disabled={isUploadingAvatar}
        />
        <Dialog open={showAvatarModal} onOpenChange={setShowAvatarModal}>
          <DialogContent className="sm:max-w-sm">
            <DialogHeader>
              <DialogTitle>{hasProfilePhoto ? "Change photo" : "Add photo"}</DialogTitle>
              <DialogDescription>
                Your photo appears in Chat, the header menu, and team member lists.
              </DialogDescription>
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
                <ImagePlus className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">
                  {isUploadingAvatar ? "Uploading…" : "Upload photo"}
                </p>
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
                  <X className="h-5 w-5 text-destructive" />
                </div>
                <div>
                  <p className="text-sm font-medium text-destructive">Remove photo</p>
                  <p className="text-xs text-muted-foreground">Revert to initials</p>
                </div>
              </button>
            ) : null}
          </DialogContent>
        </Dialog>
        <div className="flex-1 overflow-auto">
        {/* Identity header: restrained Emerald signal, no decorative AI field. */}
        <div className="relative overflow-hidden border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-[radial-gradient(circle_at_16%_0%,var(--g-emerald-pale),transparent_62%)] opacity-70" />

          <div className="relative px-6 py-8 lg:px-8">
            <div className="max-w-4xl mx-auto">
              {/* Back link with animation */}
              <Link 
                href="/settings" 
                className={cn(
                  "inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 group"
                )}
              >
                <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
                Back to settings
              </Link>

              {/* Profile Card */}
              <div className={cn(
                "flex flex-col md:flex-row items-start md:items-center gap-6"
              )}>
                {/* Avatar with upload functionality */}
                <div className="relative group">
                  <button 
                    type="button"
                    onClick={() => setShowAvatarModal(true)}
                    aria-label={hasProfilePhoto ? "Change profile photo" : "Add profile photo"}
                    className="relative flex h-24 w-24 items-center justify-center rounded-full ring-4 ring-background overflow-hidden cursor-pointer"
                  >
                    <UserAccountAvatar useCurrentUser className="h-24 w-24 text-2xl" fallbackClassName="text-2xl" />
                    {/* Hover overlay */}
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <Camera className="h-6 w-6 text-white" />
                    </div>
                  </button>
                  <button 
                    type="button"
                    onClick={() => setShowAvatarModal(true)}
                    aria-hidden="true"
                    tabIndex={-1}
                    className="absolute bottom-0 right-0 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg opacity-0 hover:scale-110 hover:bg-primary/90 group-hover:opacity-100"
                  >
                    <Camera className="h-4 w-4" />
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 md:self-center">
                  <Button type="button" variant="outline" size="sm" onClick={() => setShowAvatarModal(true)}>
                    <Camera className="mr-2 h-4 w-4" />
                    {hasProfilePhoto ? "Change photo" : "Add photo"}
                  </Button>
                  {hasProfilePhoto && (
                    <Button type="button" variant="ghost" size="sm" onClick={() => void handleRemoveAvatar()} className="text-destructive hover:text-destructive">
                      Remove photo
                    </Button>
                  )}
                </div>

                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h1 className={TYPE.pageTitle}>
                      {profile.firstName} {profile.lastName}
                    </h1>
                    <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-success/10 border border-success/20">
                      <Shield className="h-3 w-3 text-success" />
                      <span className="text-xs font-medium text-success">Verified</span>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground mb-3">
                    {profile.jobTitle} at {profile.department}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {profile.location}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      Pacific Time
                    </span>
                  </div>
                </div>

                <Button className="gap-2 bg-foreground text-background hover:bg-foreground/90" onClick={handleSaveProfile} disabled={isSaving}>
                  {isSaving ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Saving...
                    </>
                  ) : saved ? (
                    <>
                      <Check className="h-4 w-4" />
                      Saved!
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4" />
                      Save changes
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div data-composition="configure" className="px-4 py-6 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <aside className="lg:col-span-1 space-y-4" aria-label="Profile scope">
                <h2 className={TYPE.sectionTitle}>Your identity</h2>
                <p className="text-sm text-muted-foreground">Your name and profile photo identify you across the workspace. Access and permissions belong to your workspace role.</p>
                <div className="border-y border-divide py-4">
                  <p className={TYPE.eyebrow}>Your active sessions</p>
                  <p className="mt-2 text-2xl font-semibold tabular-nums">{Array.isArray(sessionsData?.sessions) ? sessionsData.sessions.length : sessionsLoading ? "Loading…" : "Not reported"}</p>
                  <a href="#profile-sessions" className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">Review devices and revoke sessions</a>
                </div>
              </aside>

              {/* Right Column - Edit Form */}
              <div className={cn(
                "lg:col-span-2 space-y-8"
              )}>
                {/* Personal Information */}
                <section>
                  <div className="flex items-center gap-2 mb-6">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                      <User className="h-4 w-4 text-primary" />
                    </div>
                    <h2 className="text-sm font-semibold text-foreground">Personal information</h2>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <InputField
                      label="First name"
                      value={profile.firstName}
                      onChange={(v) => handleChange("firstName", v)}
                      icon={User}
                      isActive={activeField === "firstName"}
                      onFocus={() => setActiveField("firstName")}
                      onBlur={() => setActiveField(null)}
                    />
                    <InputField
                      label="Last name"
                      value={profile.lastName}
                      onChange={(v) => handleChange("lastName", v)}
                      icon={User}
                      isActive={activeField === "lastName"}
                      onFocus={() => setActiveField("lastName")}
                      onBlur={() => setActiveField(null)}
                    />
                  </div>

                  <div className="mt-4">
                    <InputField
                      label="Email address"
                      value={profile.email}
                      onChange={(v) => handleChange("email", v)}
                      icon={Mail}
                      type="email"
                      isActive={activeField === "email"}
                      onFocus={() => setActiveField("email")}
                      onBlur={() => setActiveField(null)}
                    />
                  </div>

                  <div className="mt-4">
                    <InputField
                      label="Phone number"
                      value={profile.phone}
                      onChange={(v) => handleChange("phone", v)}
                      icon={Phone}
                      type="tel"
                      isActive={activeField === "phone"}
                      onFocus={() => setActiveField("phone")}
                      onBlur={() => setActiveField(null)}
                    />
                  </div>
                </section>

                {/* Work Information */}
                <section>
                  <div className="flex items-center gap-2 mb-6">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                      <Building2 className="h-4 w-4 text-primary" />
                    </div>
                    <h2 className="text-sm font-semibold text-foreground">Work information</h2>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <InputField
                      label="Job title"
                      value={profile.jobTitle}
                      onChange={(v) => handleChange("jobTitle", v)}
                      icon={Building2}
                      isActive={activeField === "jobTitle"}
                      onFocus={() => setActiveField("jobTitle")}
                      onBlur={() => setActiveField(null)}
                    />
                    <InputField
                      label="Department"
                      value={profile.department}
                      onChange={(v) => handleChange("department", v)}
                      icon={Building2}
                      isActive={activeField === "department"}
                      onFocus={() => setActiveField("department")}
                      onBlur={() => setActiveField(null)}
                    />
                  </div>

                  <div className="mt-4">
                    <InputField
                      label="Location"
                      value={profile.location}
                      onChange={(v) => handleChange("location", v)}
                      icon={MapPin}
                      isActive={activeField === "location"}
                      onFocus={() => setActiveField("location")}
                      onBlur={() => setActiveField(null)}
                    />
                  </div>

                  <div className="mt-4">
                    <label className="text-xs font-medium text-muted-foreground">
                      Timezone
                    </label>
                    <select 
                      value={profile.timezone}
                      onChange={(e) => handleChange("timezone", e.target.value)}
                      aria-label="Timezone"
                      className="mt-2 w-full h-11 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] px-4 text-sm text-foreground hover:border-muted-foreground/50 focus:border-ring focus:ring-2 focus:ring-ring/20 outline-none"
                    >
                      <option value="America/Los_Angeles">Pacific Time (PT)</option>
                      <option value="America/Denver">Mountain Time (MT)</option>
                      <option value="America/Chicago">Central Time (CT)</option>
                      <option value="America/New_York">Eastern Time (ET)</option>
                      <option value="Europe/London">GMT/UTC</option>
                      <option value="Europe/Paris">Central European Time (CET)</option>
                      <option value="Asia/Tokyo">Japan Standard Time (JST)</option>
                    </select>
                  </div>
                </section>

                {/* Bio */}
                <section>
                  <div className="flex items-center gap-2 mb-6">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                      <Activity className="h-4 w-4 text-primary" />
                    </div>
                    <h2 className="text-sm font-semibold text-foreground">About you</h2>
                  </div>
                  
                  <div className="relative group">
                    <textarea 
                      value={profile.bio}
                      onChange={(e) => handleChange("bio", e.target.value)}
                      onFocus={() => setActiveField("bio")}
                      onBlur={() => setActiveField(null)}
                      className={cn(
                        "w-full h-32 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] px-4 py-3 text-sm text-foreground resize-none outline-none",
                        activeField === "bio" 
                          ? "border-ring ring-2 ring-ring/20 shadow-lg shadow-primary/10" 
                          : "border-border hover:border-muted-foreground/50"
                      )}
                      placeholder="Tell us a bit about yourself..."
                    />
                    <div className="absolute bottom-3 right-3 text-xs text-muted-foreground">
                      {profile.bio.length}/280
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Brief description visible to your team members
                  </p>
                </section>

                {/* Security */}
                <section>
                  <div className="flex items-center gap-2 mb-6">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                      <Shield className="h-4 w-4 text-primary" />
                    </div>
                    <h2 className="text-sm font-semibold text-foreground">Security</h2>
                  </div>
                  <div className="grid grid-cols-1 gap-4">
                    <Input
                      type="password"
                      placeholder="Current password"
                      value={currentPassword}
                      onChange={(event) => setCurrentPassword(event.target.value)}
                    />
                    <Input
                      type="password"
                      placeholder="New password"
                      value={newPassword}
                      onChange={(event) => setNewPassword(event.target.value)}
                    />
                    <Input
                      type="password"
                      placeholder="Confirm new password"
                      value={confirmPassword}
                      onChange={(event) => setConfirmPassword(event.target.value)}
                    />
                    <div>
                      <Button onClick={() => void handleChangePassword()} disabled={isChangingPassword} className="gap-2">
                        {isChangingPassword && <Loader2 className="h-4 w-4 animate-spin" />}
                        Change Password
                      </Button>
                    </div>
                  </div>
                </section>

                {/* Sessions */}
                <section>
                  <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                        <Activity className="h-4 w-4 text-primary" />
                      </div>
                      <h2 id="profile-sessions" className="text-sm font-semibold text-foreground">Active sessions</h2>
                    </div>
                    <Button variant="outline" onClick={() => void handleRevokeAllSessions()} disabled={isRevokingAll} className="gap-2">
                      {isRevokingAll && <Loader2 className="h-4 w-4 animate-spin" />}
                      Revoke All
                    </Button>
                  </div>
                  <div className="space-y-3">
                    {sessionsError ? <div role="alert" className="text-sm text-destructive">Could not load sessions. <Button variant="ghost" onClick={() => void mutateSessions()}>Retry</Button></div> : null}
                    {sessionsLoading && !sessionsData ? <p className="text-sm text-muted-foreground">Loading sessions…</p> : null}
                    {(sessionsData?.sessions ?? []).map((session) => (
                      <div key={session.id} className="flex items-center justify-between rounded-[var(--np-radius-md)] border border-divide p-3">
                        <div>
                          <p className="text-sm font-medium text-foreground">{session.device}</p>
                          <p className="text-xs text-muted-foreground">{session.ip} · {session.last_active}</p>
                        </div>
                        {session.current ? (
                          <span className="text-xs font-medium text-success">Current</span>
                        ) : (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => void handleRevokeSession(session.id)}
                          >
                            Revoke
                          </Button>
                        )}
                      </div>
                    ))}
                    {Array.isArray(sessionsData?.sessions) && !sessionsError && sessionsData.sessions.length === 0 && (
                      <p className="text-xs text-muted-foreground">No active sessions found.</p>
                    )}
                  </div>
                </section>
              </div>
            </div>
          </div>
        </div>
        </div>
      </SettingsShell>
    </AppShell>
  )
}

// Enhanced Input Field Component
function InputField({ 
  label, 
  value, 
  onChange, 
  icon: Icon, 
  type = "text",
  isActive,
  onFocus,
  onBlur
}: { 
  label: string
  value: string
  onChange: (value: string) => void
  icon: React.ComponentType<{ className?: string }>
  type?: string
  isActive?: boolean
  onFocus?: () => void
  onBlur?: () => void
}) {
  const fieldId = useId()
  return (
    <div className="group">
      <label htmlFor={fieldId} className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      <div className={cn(
        "mt-2 relative rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)]",
        isActive 
          ? "border-ring ring-2 ring-ring/20 shadow-lg shadow-primary/10" 
          : "border-border hover:border-muted-foreground/50"
      )}>
        <Icon className={cn(
          "absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 transition-colors duration-200",
          isActive ? "text-primary" : "text-muted-foreground"
        )} />
        <input
          id={fieldId}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={onFocus}
          onBlur={onBlur}
          className="w-full h-11 bg-transparent pl-11 pr-4 text-sm text-foreground outline-none"
        />
      </div>
    </div>
  )
}
