// =============================================================================
// Gravitre Component Library - Unified Exports
// =============================================================================

// Layout Components
export { AppShell } from "./app-shell"
export { Sidebar } from "./sidebar"
export { TopBar } from "./top-bar"
export { PageHeader, StatsGrid, StatCard } from "./page-header"

// Card Components  
export { 
  ContentCard, 
  ContentCardHeader, 
  ContentCardBody, 
  ContentCardFooter,
  AnimatedContentCard,
  MetricCard 
} from "./content-card"
export { ActionCard } from "./action-card"
export { WorkflowCard, WorkflowGrid } from "./workflow-card"

// Badge Components
export { StatusBadge, AutoStatusBadge } from "./status-badge"
export { EnvironmentBadge } from "./environment-badge"

// List Item Components
export { SessionItem } from "./session-item"
export { TimelineItem, Timeline } from "./timeline-item"

// AI Components
export { AICommandInput } from "./ai-command-input"
export { MesonInsightsPanel, AIInsightsPanel } from "./ai-insights-panel"
export { AIPresence } from "./ai-presence"
export { AIProcessingStatus } from "./ai-processing-status"
export { ReasoningBlock } from "./reasoning-block"
export { SuggestedActions } from "./suggested-actions"

// Dialog/Modal Components
export { MesonWizard } from "./meson-wizard"
export { GlobalCommandBar } from "./global-command-bar"
export { NotificationCenter, NotificationProvider, NotificationToast, useNotifications, useNotificationsRequired } from "./notification-center"
export { UpgradePrompt } from "./upgrade-prompt"

// Data Display Components
export { DataTable } from "./data-table"
export { ContextPack } from "./context-pack"
export { GuardrailsBox } from "./guardrails-box"
export { ActionProposal } from "./action-proposal"

// Utility Components
export { IconButton } from "./icon-button"
export { VendorLogo } from "./vendor-logo"
export { ConnectorIcon, ConnectorIconGrid, ConnectorFallbackIcon } from "./connector-icon"
export { LottieAnimation } from "./lottie-animation"

// Avatar Components
export { AgentAvatar, UserAvatar, ChatMessage } from "./chat-avatars"
export { IntegrationsGrid } from "./platform-logos"

// Marketing Components
export { AppShowcase } from "./app-showcase"

// State Components
export { EmptyState, NoResultsState, NoDataState, ErrorState } from "./empty-state"
export { 
  LoadingSpinner, 
  CardSkeleton, 
  TableSkeleton, 
  ListSkeleton, 
  PageSkeleton 
} from "./loading-state"

// Form Components
export { SearchInput, DebouncedSearchInput } from "./search-input"

// Onboarding Components
export { 
  OnboardingProvider, 
  OnboardingChecklist, 
  OnboardingProgressCard,
  useOnboarding 
} from "./onboarding-checklist"

// Premium Effects & Motion Components
export {
  ParticleField,
  PulseRing,
  GlowOrb,
  NeuralNetwork,
  DataStream,
  StatusBeacon,
  MorphingBackground,
  FloatingCard,
  ActivityIndicator,
  TypingIndicator,
  ShimmerText,
  AnimatedCounter,
  GridPattern
} from "./premium-effects"
