"use client"

import { useState, useEffect, useRef } from "react"
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
import Image from "next/image"

export default function ProfilePage() {
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [activeField, setActiveField] = useState<string | null>(null)
  const [avatarImage, setAvatarImage] = useState<string | null>(null)
  const [showAvatarModal, setShowAvatarModal] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [profile, setProfile] = useState({
    firstName: "John",
    lastName: "Doe",
    email: "john@acmecorp.com",
    phone: "+1 (555) 123-4567",
    jobTitle: "Operations Manager",
    department: "Operations",
    location: "San Francisco, CA",
    timezone: "America/Los_Angeles",
    bio: "Operations manager focused on workflow automation and AI-driven process optimization."
  })

  useEffect(() => {
    setMounted(true)
  }, [])

  const handleSave = async () => {
    setIsSaving(true)
    await new Promise((resolve) => setTimeout(resolve, 1500))
    setIsSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const handleChange = (field: string, value: string) => {
    setProfile(prev => ({ ...prev, [field]: value }))
  }

  const handleAvatarUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (event) => {
        setAvatarImage(event.target?.result as string)
        setShowAvatarModal(false)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleRemoveAvatar = () => {
    setAvatarImage(null)
    setShowAvatarModal(false)
  }

  // Activity stats
  const activityStats = [
    { label: "Workflows Created", value: "47", icon: Zap, color: "text-blue-500" },
    { label: "Approvals Made", value: "156", icon: Check, color: "text-emerald-500" },
    { label: "Active Sessions", value: "3", icon: Activity, color: "text-amber-500" },
  ]

  return (
    <AppShell>
      <div className="flex-1 overflow-auto">
        {/* Hero Header with gradient */}
        <div className="relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-purple-500/5 to-pink-500/5" />
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-500/10 via-transparent to-transparent" />
          
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
                  <div className="absolute -inset-1 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 rounded-full opacity-0 group-hover:opacity-75 blur transition-all duration-500" />
                  <button 
                    onClick={() => setShowAvatarModal(true)}
                    className="relative flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-slate-800 to-slate-900 text-2xl font-semibold text-white ring-4 ring-background overflow-hidden cursor-pointer"
                  >
                    {avatarImage ? (
                      <Image 
                        src={avatarImage} 
                        alt="Profile" 
                        fill 
                        className="object-cover"
                      />
                    ) : (
                      <span>JD</span>
                    )}
                    {/* Hover overlay */}
                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <Camera className="h-6 w-6 text-white" />
                    </div>
                  </button>
                  <button 
                    onClick={() => setShowAvatarModal(true)}
                    className="absolute bottom-0 right-0 flex h-8 w-8 items-center justify-center rounded-full bg-blue-500 text-white shadow-lg opacity-0 group-hover:opacity-100 transition-all duration-300 hover:bg-blue-600 hover:scale-110"
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

                      {/* Current avatar preview */}
                      <div className="flex justify-center mb-6">
                        <div className="relative h-28 w-28 rounded-full bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center text-3xl font-semibold text-white overflow-hidden ring-4 ring-border">
                          {avatarImage ? (
                            <Image 
                              src={avatarImage} 
                              alt="Profile" 
                              fill 
                              className="object-cover"
                            />
                          ) : (
                            <span>JD</span>
                          )}
                        </div>
                      </div>

                      {/* Upload options */}
                      <div className="space-y-3">
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          className="w-full flex items-center gap-3 p-4 rounded-xl border border-border bg-secondary/30 hover:bg-secondary/50 transition-colors text-left"
                        >
                          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
                            <ImagePlus className="h-5 w-5 text-blue-500" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-foreground">Upload new photo</p>
                            <p className="text-xs text-muted-foreground">JPG, PNG or GIF, max 5MB</p>
                          </div>
                        </button>

                        {avatarImage && (
                          <button
                            onClick={handleRemoveAvatar}
                            className="w-full flex items-center gap-3 p-4 rounded-xl border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 transition-colors text-left"
                          >
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/10">
                              <X className="h-5 w-5 text-red-500" />
                            </div>
                            <div>
                              <p className="text-sm font-medium text-red-500">Remove photo</p>
                              <p className="text-xs text-red-400/70">Revert to initials</p>
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
                    <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                      <Shield className="h-3 w-3 text-emerald-500" />
                      <span className="text-xs font-medium text-emerald-500">Verified</span>
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

                <Button className="gap-2 bg-foreground text-background hover:bg-foreground/90" onClick={handleSave} disabled={isSaving}>
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
                <div className={cn(
                  "relative overflow-hidden rounded-xl border border-purple-500/20 bg-gradient-to-br from-purple-500/5 to-pink-500/5 p-4 transition-all duration-500 delay-500",
                  mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                )}>
                  <div className="absolute top-0 right-0 w-32 h-32 bg-purple-500/10 rounded-full blur-2xl -translate-y-1/2 translate-x-1/2" />
                  <div className="relative">
                    <div className="flex items-center gap-2 mb-3">
                      <Sparkles className="h-4 w-4 text-purple-500" />
                      <span className="text-xs font-medium text-purple-500 uppercase tracking-wider">Meson Insight</span>
                    </div>
                    <p className="text-sm text-foreground leading-relaxed">
                      You&apos;ve approved <span className="font-semibold text-purple-500">23% more</span> workflow requests this month. Your team is becoming more autonomous!
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
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
                      <User className="h-4 w-4 text-blue-500" />
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
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
                      <Building2 className="h-4 w-4 text-emerald-500" />
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
                      className="mt-2 w-full h-11 rounded-xl border border-border bg-card px-4 text-sm text-foreground transition-all duration-200 hover:border-muted-foreground/50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none"
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
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber-500/10">
                      <Sparkles className="h-4 w-4 text-amber-500" />
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
                          ? "border-blue-500 ring-2 ring-blue-500/20 shadow-lg shadow-blue-500/10" 
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
              </div>
            </div>
          </div>
        </div>
      </div>
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
  return (
    <div className="group">
      <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </label>
      <div className={cn(
        "mt-2 relative rounded-xl border bg-card transition-all duration-300",
        isActive 
          ? "border-blue-500 ring-2 ring-blue-500/20 shadow-lg shadow-blue-500/10" 
          : "border-border hover:border-muted-foreground/50"
      )}>
        <Icon className={cn(
          "absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 transition-colors duration-200",
          isActive ? "text-blue-500" : "text-muted-foreground"
        )} />
        <input
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
