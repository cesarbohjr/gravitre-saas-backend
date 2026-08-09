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
  Upload,
  ArrowLeft,
  User,
  Mail,
  Phone,
  Building2,
  MapPin,
  Sparkles,
  Shield,
  Clock,
  Activity,
  Zap,
  Camera,
  X,
  ImagePlus
} from "lucide-react"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { useUserProfile } from "@/lib/user-profile-context"
import { useAuth } from "@/lib/auth-context"
import { authApi } from "@/lib/api"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { toast } from "sonner"
import { mutate as globalMutate } from "swr"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { SettingsShell } from "@/components/settings/settings-shell"
import { useOrgAdmin } from "@/lib/use-org-admin"

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
  const { isAdmin } = useOrgAdmin()
  const { profile, updateProfile, setAvatarImage: setContextAvatarImage, getInitials } = useUserProfile()
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const mounted = true
  const [activeField, setActiveField] = useState<string | null>(null)
  const [showAvatarModal, setShowAvatarModal] = useState(false)
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [isRevokingAll, setIsRevokingAll] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { data: sessionsData, mutate: mutateSessions } = useSWR<AuthSessionsResponse>(
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
    const file = e.target.files?.[0]
    if (file) {
      try {
        const response = await authApi.uploadAvatar(file)
        setContextAvatarImage(response.avatar_url)
        await globalMutate("account-profile-me")
        toast.success("Profile photo updated")
        setShowAvatarModal(false)
      } catch (err) {
        console.error("[v0] Avatar upload failed:", err)
        toast.error("Failed to upload profile photo")
      }
    }
  }

  const handleRemoveAvatar = async () => {
    try {
      await authApi.removeAvatar()
      setContextAvatarImage(null)
      await globalMutate("account-profile-me")
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

  // Activity stats
  const activityStats = [
    // Three unrelated metrics, so the categorical --chart-* ramp rather than
    // health tones (an amber session count doesn't mean anything is wrong).
    { label: "Workflows Created", value: "47", icon: Zap, color: "text-chart-2" },
    { label: "Approvals Made", value: "156", icon: Check, color: "text-chart-1" },
    { label: "Active Sessions", value: "3", icon: Activity, color: "text-chart-3" },
  ]

  if (loading) {
    return (
      <AppShell title="Settings">
        <SettingsShell activeSection="profile" isAdmin={isAdmin} hideHeader>
          <CenteredLoader fill="parent" label="Loading profile" />
        </SettingsShell>
      </AppShell>
    )
  }

  return (
    <AppShell title="Settings">
      <SettingsShell activeSection="profile" isAdmin={isAdmin} hideHeader>
        <div className="flex-1 overflow-auto">
        {/* Hero Header with gradient */}
        <div className="relative overflow-hidden">
          {/* Was blue -> purple -> pink; purple and pink appear nowhere else in
              the product, so the hero read as a generic template rather than
              this app. Now a single brand-primary wash. */}
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 via-transparent to-transparent" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-primary/10 via-transparent to-transparent" />
          
          {/* Animated grid pattern */}
          <div className="absolute inset-0 opacity-[0.02]" style={{
            backgroundImage: `linear-gradient(rgba(255,255,255,.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.1) 1px, transparent 1px)`,
            backgroundSize: '32px 32px'
          }} />

          <div className="relative px-6 py-8 lg:px-8">
            <div className="max-w-4xl mx-auto">
              {/* Back link with animation */}
              <Link 
                href="/settings" 
                className={cn(
                  "inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-all duration-300 group",
                  mounted ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-4"
                )}
              >
                <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
                Back to Settings
              </Link>

              {/* Profile Card */}
              <div className={cn(
                "flex flex-col md:flex-row items-start md:items-center gap-6 transition-all duration-500 delay-100",
                mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              )}>
                {/* Avatar with upload functionality */}
                <div className="relative group">
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleAvatarUpload}
                    accept="image/*"
                    className="hidden"
                  />
                  <div className="absolute -inset-1 rounded-full bg-primary opacity-0 blur transition-all duration-500 group-hover:opacity-60" />
                  <button 
                    type="button"
                    onClick={() => setShowAvatarModal(true)}
                    aria-label="Change profile photo"
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
                    className="absolute bottom-0 right-0 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg opacity-0 transition-all duration-300 hover:scale-110 hover:bg-primary/90 group-hover:opacity-100"
                  >
                    <Camera className="h-4 w-4" />
                  </button>
                </div>

                {/* Avatar Upload Modal */}
                {showAvatarModal && (
                  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={() => setShowAvatarModal(false)}>
                    <div 
                      className="bg-card border border-border rounded-2xl p-6 w-full max-w-sm mx-4 shadow-2xl"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="flex items-center justify-between mb-6">
                        <h3 className="text-lg font-semibold text-foreground">Update Profile Photo</h3>
                        <button 
                          onClick={() => setShowAvatarModal(false)}
                          className="p-1.5 rounded-lg hover:bg-secondary transition-colors"
                        >
                          <X className="h-5 w-5 text-muted-foreground" />
                        </button>
                      </div>

                      <p className="mb-6 text-center text-xs text-muted-foreground">
                        Your photo appears in Chat, the header menu, and team member lists.
                      </p>

                      {/* Current avatar preview */}
                      <div className="flex justify-center mb-6">
                        <UserAccountAvatar useCurrentUser className="h-28 w-28 text-3xl" fallbackClassName="text-3xl" />
                      </div>

                      {/* Upload options */}
                      <div className="space-y-3">
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="w-full flex items-center gap-3 p-4 rounded-xl border border-border bg-secondary/30 hover:bg-secondary/50 transition-colors text-left"
                        >
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                            <ImagePlus className="h-5 w-5 text-primary" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-foreground">Upload new photo</p>
                            <p className="text-xs text-muted-foreground">JPG, PNG or GIF, max 5MB</p>
                          </div>
                        </button>

                        {profile.avatarImage && (
                          <button
                            onClick={() => void handleRemoveAvatar()}
                            className="w-full flex items-center gap-3 p-4 rounded-xl border border-destructive/20 bg-destructive/5 hover:bg-destructive/10 transition-colors text-left"
                          >
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-destructive/10">
                              <X className="h-5 w-5 text-destructive" />
                            </div>
                            <div>
                              <p className="text-sm font-medium text-destructive">Remove photo</p>
                              {/* Was text-red-400/70 — a light tint at 70% opacity
                                  on a light background, which failed contrast. */}
                              <p className="text-xs text-muted-foreground">Revert to initials</p>
                            </div>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h1 className="text-2xl font-semibold text-foreground">
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
                      Save Changes
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="px-6 py-8 lg:px-8">
          <div className="max-w-4xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Column - Activity Stats */}
              <div className={cn(
                "lg:col-span-1 space-y-4 transition-all duration-500 delay-200",
                mounted ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-8"
              )}>
                <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  Activity Overview
                </h2>
                {activityStats.map((stat, i) => (
                  <div 
                    key={stat.label}
                    className={cn(
                      "group relative overflow-hidden rounded-xl border border-border bg-card p-4 transition-all duration-300 hover:border-border/80 hover:shadow-lg hover:shadow-black/5",
                      mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                    )}
                    style={{ transitionDelay: `${300 + i * 100}ms` }}
                  >
                    <div className="absolute inset-0 bg-gradient-to-br from-transparent to-black/[0.02] group-hover:to-black/[0.04] transition-colors" />
                    <div className="relative flex items-center gap-3">
                      <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg bg-secondary", stat.color)}>
                        <stat.icon className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="text-2xl font-semibold text-foreground">{stat.value}</p>
                        <p className="text-xs text-muted-foreground">{stat.label}</p>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Meson Insights Card */}
                {/* Meson's sub-brand is violet everywhere else (the wizard, its
                    launch trigger), so this card used the wrong accent —
                    purple/pink appear nowhere else in the product. */}
                <div className={cn(
                  "relative overflow-hidden rounded-xl border border-violet-500/20 bg-violet-500/5 p-4 transition-all duration-500 delay-500",
                  mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                )}>
                  <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/10 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2" />
                  <div className="relative">
                    <div className="flex items-center gap-2 mb-3">
                      <Sparkles className="h-4 w-4 text-violet-600 dark:text-violet-400" />
                      <span className="text-xs font-medium uppercase tracking-wider text-violet-600 dark:text-violet-400">
                        Meson Insight
                      </span>
                    </div>
                    <p className="text-sm text-foreground leading-relaxed">
                      You&apos;ve approved{" "}
                      <span className="font-semibold text-violet-600 dark:text-violet-400">23% more</span>{" "}
                      workflow requests this month. Your team is becoming more autonomous.
                    </p>
                  </div>
                </div>
              </div>

              {/* Right Column - Edit Form */}
              <div className={cn(
                "lg:col-span-2 space-y-8 transition-all duration-500 delay-300",
                mounted ? "opacity-100 translate-x-0" : "opacity-0 translate-x-8"
              )}>
                {/* Personal Information */}
                <section>
                  <div className="flex items-center gap-2 mb-6">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                      <User className="h-4 w-4 text-primary" />
                    </div>
                    <h2 className="text-sm font-semibold text-foreground">Personal Information</h2>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <InputField
                      label="First Name"
                      value={profile.firstName}
                      onChange={(v) => handleChange("firstName", v)}
                      icon={User}
                      isActive={activeField === "firstName"}
                      onFocus={() => setActiveField("firstName")}
                      onBlur={() => setActiveField(null)}
                    />
                    <InputField
                      label="Last Name"
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
                      label="Email Address"
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
                      label="Phone Number"
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
                    <h2 className="text-sm font-semibold text-foreground">Work Information</h2>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <InputField
                      label="Job Title"
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
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Timezone
                    </label>
                    <select 
                      value={profile.timezone}
                      onChange={(e) => handleChange("timezone", e.target.value)}
                      aria-label="Timezone"
                      className="mt-2 w-full h-11 rounded-xl border border-border bg-card px-4 text-sm text-foreground transition-all duration-200 hover:border-muted-foreground/50 focus:border-ring focus:ring-2 focus:ring-ring/20 outline-none"
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
                      <Sparkles className="h-4 w-4 text-primary" />
                    </div>
                    <h2 className="text-sm font-semibold text-foreground">About You</h2>
                  </div>
                  
                  <div className="relative group">
                    <textarea 
                      value={profile.bio}
                      onChange={(e) => handleChange("bio", e.target.value)}
                      onFocus={() => setActiveField("bio")}
                      onBlur={() => setActiveField(null)}
                      className={cn(
                        "w-full h-32 rounded-xl border bg-card px-4 py-3 text-sm text-foreground resize-none transition-all duration-300 outline-none",
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
                      <h2 className="text-sm font-semibold text-foreground">Active Sessions</h2>
                    </div>
                    <Button variant="outline" onClick={() => void handleRevokeAllSessions()} disabled={isRevokingAll} className="gap-2">
                      {isRevokingAll && <Loader2 className="h-4 w-4 animate-spin" />}
                      Revoke All
                    </Button>
                  </div>
                  <div className="space-y-3">
                    {(sessionsData?.sessions ?? []).map((session) => (
                      <div key={session.id} className="flex items-center justify-between rounded-lg border border-border p-3">
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
                    {(sessionsData?.sessions ?? []).length === 0 && (
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
      <label htmlFor={fieldId} className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </label>
      <div className={cn(
        "mt-2 relative rounded-xl border bg-card transition-all duration-300",
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
