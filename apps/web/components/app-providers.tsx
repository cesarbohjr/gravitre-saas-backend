"use client"

import type { ReactNode } from "react"
import { ThemeProvider } from "@/components/theme-provider"
import { MotionProvider } from "@/components/motion-provider"
import { ViewModeProvider } from "@/lib/view-mode-context"
import { Toaster } from "@/components/ui/sonner"
import { NotificationProvider } from "@/components/gravitre/notification-center"
import { OnboardingProvider, OnboardingChecklist } from "@/components/gravitre/onboarding-checklist"
import { AuthProvider } from "@/lib/auth-context"
import { OrgSyncBootstrap } from "@/components/gravitre/org-sync-bootstrap"
import { EnterpriseBrandingProvider } from "@/lib/enterprise-branding-context"
import { EntitlementsProvider } from "@/lib/entitlements-context"
import { UserProfileProvider } from "@/lib/user-profile-context"
import { AccountProfileSync } from "@/components/gravitre/account-profile-sync"
import { GravitreAIWorkspaceProvider } from "@/components/gravitre/ai-workspace-provider"
import { AiFullPageSlotProvider } from "@/components/gravitre/ai-full-page-slot"
import { GravitreAIWorkspaceHost } from "@/components/gravitre/ai-workspace-host"
import { GravitreAIHelper } from "@/components/gravitre/ai-helper"
import { GravitreAIShortcutListener } from "@/components/gravitre/ai-shortcut-listener"
import { GravitreAIPresenceAnnouncer } from "@/components/gravitre/ai-presence-announcer"

/**
 * Full signed-in operator shell — mounted only on non-marketing routes.
 */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      forcedTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      <MotionProvider>
        <AuthProvider>
          <OrgSyncBootstrap />
          <EnterpriseBrandingProvider>
            <EntitlementsProvider>
              <UserProfileProvider>
                <AccountProfileSync />
                <NotificationProvider>
                  <OnboardingProvider>
                    <ViewModeProvider>
                      {/*
                        Mounted once, above every per-page <AppShell> — see
                        docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
                        Finding A5 / Part B1. Must never move inside a
                        per-page tree, or it loses the one property Phase 2+
                        depends on: surviving route navigation unremounted.
                      */}
                      <GravitreAIWorkspaceProvider>
                        <AiFullPageSlotProvider>
                          {children}
                          <GravitreAIWorkspaceHost />
                          <GravitreAIHelper />
                          <GravitreAIShortcutListener />
                          <GravitreAIPresenceAnnouncer />
                        </AiFullPageSlotProvider>
                      </GravitreAIWorkspaceProvider>
                    </ViewModeProvider>
                    <OnboardingChecklist />
                  </OnboardingProvider>
                </NotificationProvider>
              </UserProfileProvider>
            </EntitlementsProvider>
          </EnterpriseBrandingProvider>
          <Toaster position="bottom-right" />
        </AuthProvider>
      </MotionProvider>
    </ThemeProvider>
  )
}
