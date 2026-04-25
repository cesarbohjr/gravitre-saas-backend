"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { supabaseClient } from "@/lib/supabaseClient"

export default function HomePage() {
  const router = useRouter()
  
  useEffect(() => {
    let mounted = true
    supabaseClient.auth.getSession().then(({ data }) => {
      if (!mounted) return
      router.replace(data.session ? "/operator" : "/login")
    })
    return () => {
      mounted = false
    }
  }, [router])

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="flex items-center gap-2 text-muted-foreground">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        <span className="text-sm">Loading...</span>
      </div>
    </div>
  )
}
