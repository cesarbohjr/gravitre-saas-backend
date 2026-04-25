# Gravitre Frontend → Backend Engineering Handoff

**Date:** April 23, 2026  
**Author:** Frontend Lead  
**Status:** Production-Ready Audit  

---

## 1. FRONTEND PURPOSE & PRODUCT INTENT

### What the product currently appears to be (based ONLY on UI)
Gravitre is an **AI Operations Platform** - a SaaS product enabling businesses to deploy, manage, and orchestrate AI agents that automate business workflows across connected tools and data sources.

### What problem it solves
- Automates repetitive business operations (syncing data, generating reports, processing workflows)
- Provides AI-powered assistance for operations teams
- Enables non-technical users ("Lite" users) to delegate work to AI agents
- Gives admin users full control over AI agent configuration, workflow building, and system integrations

### System type
**Multi-tenant SaaS platform** with:
- AI agent orchestration engine
- Visual workflow builder
- Multi-system integration hub
- Role-based access (Admin vs Lite users)

### User types that exist
| User Type | Access Level | Routes | Status |
|-----------|-------------|--------|--------|
| Admin | Full platform access | `/operator`, `/agents`, `/workflows`, `/settings`, etc. | VISUALLY PRESENT |
| Lite User | Simplified task assignment | `/lite/*` routes only | VISUALLY PRESENT |
| Marketing (public) | Public pages only | `/(marketing)/*` | VISUALLY PRESENT |

### What is real vs aspirational
| Feature | Status |
|---------|--------|
| Marketing site | PRODUCTION-READY (static) |
| Admin dashboard UI | PRODUCTION-READY (static data) |
| Lite user UI | PRODUCTION-READY (static data) |
| AI Operator chat | PLACEHOLDER (no real AI) |
| Agent execution | PLACEHOLDER (mock data) |
| Workflow execution | PLACEHOLDER (mock data) |
| Billing/Stripe | PLACEHOLDER (no integration) |
| Authentication | NOT IMPLEMENTED |
| Database | NOT IMPLEMENTED |

---

## 2. FRONTEND ARCHITECTURE ASSUMPTIONS

### Framework
- **Next.js 15+** (App Router)
- **React 18+** with Server Components
- **TypeScript** throughout

### Routing structure
```
app/
├── (marketing)/          # Public marketing site (separate layout)
│   ├── page.tsx          # Homepage
│   ├── login/            # Login form (UI only)
│   ├── pricing/          # Pricing page
│   ├── features/         # Features page
│   └── ...
├── page.tsx              # Redirects to /operator
├── operator/             # AI Assistant (admin)
├── agents/               # Agent management
├── workflows/            # Workflow builder
├── settings/             # Settings (billing, org, etc.)
├── lite/                 # Lite user portal
│   ├── page.tsx          # Lite dashboard
│   ├── assign/           # Task assignment
│   ├── tasks/            # Task tracking
│   └── deliverables/     # Output viewing
└── api/                  # API routes (mock data)
```

### State management
- **Client-side only** via React `useState`
- **SWR** for data fetching (currently hitting mock API routes)
- **localStorage** for view mode persistence (`admin` | `lite`)
- **Context API** for:
  - `ViewModeProvider` (admin/lite toggle)
  - `NotificationProvider` (toast notifications)
  - `OnboardingProvider` (checklist state)

### Where frontend expects server interaction
| Location | Expected API | Current State |
|----------|-------------|---------------|
| `/operator` | AI chat/completion endpoint | MOCK |
| `/agents` | CRUD for agents | MOCK at `/api/agents` |
| `/workflows` | CRUD for workflows | MOCK at `/api/workflows` |
| `/runs` | Run history/status | MOCK at `/api/runs` |
| `/approvals` | Approval queue | MOCK at `/api/approvals` |
| `/metrics` | Dashboard analytics | MOCK at `/api/metrics/*` |
| `/settings/billing` | Stripe integration | PLACEHOLDER |
| `/login` | Authentication | NOT IMPLEMENTED |
| `/onboarding` | User setup flow | CLIENT-ONLY |

### Auth/session assumptions
- **NONE IMPLEMENTED** - No authentication exists
- UI assumes authenticated state throughout app routes
- Marketing routes are public
- No session management, no JWT, no cookies
- **CRITICAL GAP**: Must implement before deployment

### Organization structure assumptions
- UI implies multi-tenant (organization name in settings)
- "Workspaces" / "Environments" concept exists in UI
- Team members section exists (placeholder)
- **No actual org/tenant isolation implemented**

---

## 3. CURRENT PAGE / SCREEN INVENTORY

### Marketing Site (Public)

| Page | Classification | Status | Backend Dependencies |
|------|---------------|--------|---------------------|
| Homepage `/` | VISUALLY PRESENT | production-ready | None (static) |
| Features `/features` | VISUALLY PRESENT | production-ready | None (static) |
| Pricing `/pricing` | VISUALLY PRESENT | production-ready | Stripe for real pricing |
| Login `/login` | VISUALLY PRESENT | partial | Auth provider |
| Get Started `/get-started` | VISUALLY PRESENT | partial | Auth + onboarding API |
| Docs `/docs` | VISUALLY PRESENT | placeholder | Documentation CMS |
| Blog `/blog` | VISUALLY PRESENT | placeholder | Blog CMS |
| About `/about` | VISUALLY PRESENT | production-ready | None (static) |
| Careers `/careers` | VISUALLY PRESENT | placeholder | Jobs API |
| Contact `/contact` | VISUALLY PRESENT | partial | Contact form API |

### Admin App Routes

| Page | Classification | Status | Backend Dependencies |
|------|---------------|--------|---------------------|
| AI Operator `/operator` | VISUALLY PRESENT | placeholder | AI completion API, runs API |
| Agents List `/agents` | VISUALLY PRESENT | partial | Agents CRUD API |
| Agent Detail `/agents/[id]` | VISUALLY PRESENT | partial | Agent API + runs |
| Agent Memory `/agents/[id]/memory` | VISUALLY PRESENT | placeholder | Vector DB / memory API |
| New Agent `/agents/new` | VISUALLY PRESENT | partial | Agent creation API |
| Workflows List `/workflows` | VISUALLY PRESENT | partial | Workflows CRUD API |
| Workflow Detail `/workflows/[id]` | VISUALLY PRESENT | partial | Workflow API |
| Workflow Builder `/workflows/[id]/builder` | VISUALLY PRESENT | partial | Workflow save/execute API |
| Workflow Schedules `/workflows/[id]/schedules` | VISUALLY PRESENT | placeholder | Cron/scheduler API |
| Runs List `/runs` | VISUALLY PRESENT | partial | Runs API |
| Run Detail `/runs/[id]` | VISUALLY PRESENT | partial | Run detail + logs API |
| Approvals `/approvals` | VISUALLY PRESENT | partial | Approvals API |
| Metrics `/metrics` | VISUALLY PRESENT | placeholder | Analytics API |
| Connectors `/connectors` | VISUALLY PRESENT | placeholder | OAuth + integrations API |
| Data Sources `/sources` | VISUALLY PRESENT | placeholder | Data ingestion API |
| Source Detail `/sources/[id]` | VISUALLY PRESENT | placeholder | Source config API |
| Integrations `/integrations` | VISUALLY PRESENT | placeholder | Integration marketplace API |
| Settings `/settings` | VISUALLY PRESENT | partial | User/org settings API |
| Billing `/settings/billing` | VISUALLY PRESENT | placeholder | Stripe API |
| Organizations `/settings/organizations` | VISUALLY PRESENT | placeholder | Org management API |
| Profile `/settings/profile` | VISUALLY PRESENT | placeholder | User profile API |
| Environments `/environments` | VISUALLY PRESENT | placeholder | Environment config API |
| Audit `/audit` | VISUALLY PRESENT | placeholder | Audit log API |
| Training `/training` | VISUALLY PRESENT | placeholder | Training data API |
| Chat `/chat` | VISUALLY PRESENT | placeholder | Search/chat API |
| Notifications `/notifications` | VISUALLY PRESENT | partial | Notifications API |
| Deliverables `/deliverables` | VISUALLY PRESENT | placeholder | Outputs API |
| Tasks `/tasks` | VISUALLY PRESENT | placeholder | Tasks API |
| Assignments `/assignments` | VISUALLY PRESENT | placeholder | Assignments API |
| Onboarding `/onboarding` | VISUALLY PRESENT | partial | Onboarding state API |

### Lite User Routes

| Page | Classification | Status | Backend Dependencies |
|------|---------------|--------|---------------------|
| Lite Home `/lite` | VISUALLY PRESENT | partial | Tasks + agents API |
| Assign Work `/lite/assign` | VISUALLY PRESENT | partial | Task creation API |
| My Tasks `/lite/tasks` | VISUALLY PRESENT | partial | Tasks API |
| Task Executing `/lite/tasks/executing` | VISUALLY PRESENT | placeholder | Real-time task status |
| Deliverables `/lite/deliverables` | VISUALLY PRESENT | placeholder | Outputs API |
| Results `/lite/results` | VISUALLY PRESENT | placeholder | Analytics API |

---

## 4. COMPONENT SYSTEM INVENTORY

### Core Layout Components

| Component | Classification | Readiness | Backend Dependencies |
|-----------|---------------|-----------|---------------------|
| `AppShell` | VISUALLY PRESENT | production-ready | None |
| `Sidebar` | VISUALLY PRESENT | production-ready | User role (view mode) |
| `TopBar` | VISUALLY PRESENT | production-ready | User data, notifications |
| `MarketingLayout` | VISUALLY PRESENT | production-ready | None |

### Gravitre-Specific Components

| Component | Purpose | Readiness | Dependencies |
|-----------|---------|-----------|--------------|
| `AICommandInput` | Chat input for AI Operator | partial | AI completion API |
| `AIInsightsPanel` | Display AI analysis | partial | AI response structure |
| `AIPresence` | Visual AI status indicator | production-ready | None |
| `AIProcessingStatus` | Loading states for AI | production-ready | None |
| `ActionCard` | Quick action cards | production-ready | None |
| `ActionProposal` | AI suggested actions | partial | Action execution API |
| `DataTable` | Reusable data tables | production-ready | Data source |
| `EmptyState` | Empty state patterns | production-ready | None |
| `GlobalCommandBar` | Cmd+K command palette | partial | Search API |
| `GuardrailsBox` | Safety controls display | partial | Guardrails config |
| `LoadingState` | Loading skeletons | production-ready | None |
| `ModelSelector` | AI model selection | production-ready | Model config API |
| `NotificationCenter` | Notifications panel | partial | Notifications API |
| `OnboardingChecklist` | Onboarding progress | partial | User progress API |
| `PageHeader` | Page title/actions | production-ready | None |
| `ReasoningBlock` | AI reasoning display | partial | AI response structure |
| `SearchInput` | Search component | partial | Search API |
| `SessionItem` | Chat session display | partial | Chat history API |
| `StatusBadge` | Status indicators | production-ready | None |
| `SuggestedActions` | AI action suggestions | partial | Action config |
| `TimelineItem` | Activity timeline | production-ready | Activity data |
| `UpgradePrompt` | Upgrade CTA | production-ready | Subscription status |
| `WorkflowCard` | Workflow preview | partial | Workflow data |

### UI Component Library (shadcn/ui)
Full component library present and production-ready:
- `Button`, `Input`, `Card`, `Dialog`, `Sheet`, `Tabs`, `Table`, `Form`, `Select`, `Checkbox`, `Switch`, `Tooltip`, `Popover`, `Command`, etc.

---

## 5. USER FLOWS (END-TO-END THINKING)

### Flow 1: Signup → Onboarding → First Value

| Step | Classification | Status | Backend Required |
|------|---------------|--------|-----------------|
| Visit homepage | VISUALLY PRESENT | Ready | None |
| Click "Get Started" | VISUALLY PRESENT | Ready | None |
| Enter email/password | VISUALLY PRESENT | BROKEN | Auth API |
| Email verification | STRONGLY IMPLIED | NOT BUILT | Email service |
| Onboarding wizard | VISUALLY PRESENT | Partial | User creation, org creation |
| Select role | VISUALLY PRESENT | Ready | Save to user profile |
| Connect first tool | VISUALLY PRESENT | PLACEHOLDER | OAuth integrations |
| First AI task | VISUALLY PRESENT | PLACEHOLDER | AI API |
| Dashboard | VISUALLY PRESENT | Partial | Metrics API |

**Breakpoints:**
- NO AUTHENTICATION - entire flow broken
- No email verification
- No actual tool connections
- No real AI execution

**Launch-critical:** YES

---

### Flow 2: AI Operator Usage

| Step | Classification | Status | Backend Required |
|------|---------------|--------|-----------------|
| Navigate to Operator | VISUALLY PRESENT | Ready | Auth |
| Enter task description | VISUALLY PRESENT | Ready | None |
| AI analyzes task | VISUALLY PRESENT | PLACEHOLDER | AI completion API |
| AI suggests actions | VISUALLY PRESENT | MOCK | Action planning API |
| User approves action | VISUALLY PRESENT | MOCK | Approval API |
| Action executes | VISUALLY PRESENT | PLACEHOLDER | Execution engine |
| Results displayed | VISUALLY PRESENT | MOCK | Results API |

**Breakpoints:**
- No real AI integration
- No actual execution engine
- Mock data only

**Launch-critical:** YES (core feature)

---

### Flow 3: Billing & Subscription

| Step | Classification | Status | Backend Required |
|------|---------------|--------|-----------------|
| View current plan | VISUALLY PRESENT | MOCK | Subscription API |
| Click upgrade | VISUALLY PRESENT | Ready | None |
| Select new plan | VISUALLY PRESENT | Ready | None |
| Enter payment | VISUALLY PRESENT | PLACEHOLDER | Stripe Checkout |
| Confirm subscription | STRONGLY IMPLIED | NOT BUILT | Stripe webhooks |
| Plan activated | STRONGLY IMPLIED | NOT BUILT | Subscription update |

**Breakpoints:**
- No Stripe integration
- No subscription management
- No usage-based billing

**Launch-critical:** YES (for paid launch)

---

### Flow 4: Agent Creation & Management

| Step | Classification | Status | Backend Required |
|------|---------------|--------|-----------------|
| Navigate to Agents | VISUALLY PRESENT | Ready | Agents API |
| Click "New Agent" | VISUALLY PRESENT | Ready | None |
| Define purpose | VISUALLY PRESENT | Ready | None |
| Select capabilities | VISUALLY PRESENT | Ready | Capabilities config |
| Connect systems | VISUALLY PRESENT | PLACEHOLDER | OAuth integrations |
| Set guardrails | VISUALLY PRESENT | Ready | Guardrails config |
| Create agent | VISUALLY PRESENT | MOCK | Agent creation API |
| Agent appears in list | VISUALLY PRESENT | MOCK | Agents API |

**Breakpoints:**
- No actual agent persistence
- No system connections
- No execution capability

**Launch-critical:** YES

---

### Flow 5: Workflow Building

| Step | Classification | Status | Backend Required |
|------|---------------|--------|-----------------|
| Navigate to Workflows | VISUALLY PRESENT | Ready | Workflows API |
| Create new workflow | VISUALLY PRESENT | Ready | None |
| Add nodes (drag/drop) | VISUALLY PRESENT | Partial | None |
| Configure nodes | VISUALLY PRESENT | Partial | None |
| Connect nodes | VISUALLY PRESENT | PLACEHOLDER | None |
| Save workflow | VISUALLY PRESENT | MOCK | Workflow save API |
| Test workflow | VISUALLY PRESENT | PLACEHOLDER | Execution API |
| Activate workflow | VISUALLY PRESENT | MOCK | Activation API |

**Breakpoints:**
- Node connections not fully functional
- No actual execution
- No save persistence

**Launch-critical:** YES

---

## 6. DATA CONTRACT EXPECTATIONS

### User
```typescript
interface User {
  id: string
  email: string
  name: string
  avatarUrl?: string
  role: "admin" | "member" | "lite"
  organizationId: string
  createdAt: string
  onboardingCompleted: boolean
  preferences: {
    defaultModel: string
    theme: "light" | "dark" | "system"
  }
}
```
**Classification:** STRONGLY IMPLIED  
**Usage:** TopBar avatar, settings, permissions

### Organization
```typescript
interface Organization {
  id: string
  name: string
  slug: string
  logoUrl?: string
  plan: "node" | "control" | "command" | "enterprise"
  subscriptionStatus: "active" | "past_due" | "canceled"
  billingEmail: string
  createdAt: string
  settings: {
    defaultEnvironment: string
    allowedModels: string[]
    guardrailsEnabled: boolean
  }
}
```
**Classification:** STRONGLY IMPLIED  
**Usage:** Settings, billing, org management

### Agent
```typescript
interface Agent {
  id: string
  name: string
  description: string
  status: "active" | "draft" | "paused" | "error"
  organizationId: string
  createdById: string
  activeVersion: string | null
  environment: "production" | "staging"
  capabilities: string[]
  connectedSystems: string[]
  guardrails: string[]
  defaultModel: string
  avatarColor: string
  workflowCount: number
  createdAt: string
  updatedAt: string
}
```
**Classification:** VISUALLY PRESENT (mock data exists)  
**Usage:** Agent list, detail, assignment

### Workflow
```typescript
interface Workflow {
  id: string
  name: string
  description: string
  status: "active" | "paused" | "draft"
  organizationId: string
  createdById: string
  environment: "production" | "staging"
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  schedule?: string // cron expression
  lastRun?: string
  successRate: string
  runCount: number
  createdAt: string
  updatedAt: string
}

interface WorkflowNode {
  id: string
  type: "trigger" | "agent" | "task" | "condition" | "action"
  name: string
  position: { x: number, y: number }
  config: Record<string, unknown>
}

interface WorkflowEdge {
  id: string
  source: string
  target: string
  condition?: string
}
```
**Classification:** VISUALLY PRESENT (mock data exists)  
**Usage:** Workflow list, builder, execution

### Run
```typescript
interface Run {
  id: string
  workflowId: string
  workflowName: string
  agentId?: string
  status: "pending" | "running" | "completed" | "failed" | "cancelled"
  approvalStatus: "not_required" | "pending" | "approved" | "rejected"
  environment: "production" | "staging"
  triggeredBy: "schedule" | "manual" | "api" | "webhook"
  triggeredById?: string
  startedAt: string
  completedAt?: string
  duration: string
  logs: RunLog[]
  outputs?: Record<string, unknown>
  error?: string
}

interface RunLog {
  timestamp: string
  level: "info" | "warn" | "error"
  message: string
  nodeId?: string
}
```
**Classification:** VISUALLY PRESENT (mock data exists)  
**Usage:** Runs list, detail, operator

### Task (Assignment)
```typescript
interface Task {
  id: string
  title: string
  description: string
  status: "pending" | "assigned" | "running" | "reviewing" | "completed" | "failed"
  assignedToAgentId: string
  createdById: string
  organizationId: string
  priority: "low" | "medium" | "high"
  dueDate?: string
  deliverables: Deliverable[]
  createdAt: string
  updatedAt: string
}
```
**Classification:** STRONGLY IMPLIED  
**Usage:** Lite user tasks, assignments

### Deliverable
```typescript
interface Deliverable {
  id: string
  taskId: string
  type: "report" | "email" | "segment" | "analysis" | "document"
  title: string
  content: Record<string, unknown>
  confidence: number
  status: "ready" | "approved" | "rejected" | "revision_requested"
  createdAt: string
}
```
**Classification:** STRONGLY IMPLIED  
**Usage:** Deliverables list, review

### Integration
```typescript
interface Integration {
  id: string
  name: string
  provider: string
  type: "oauth" | "api_key" | "database"
  status: "connected" | "disconnected" | "error"
  organizationId: string
  credentials: Record<string, unknown> // encrypted
  lastSyncAt?: string
  config: Record<string, unknown>
}
```
**Classification:** VISUALLY PRESENT (placeholder)  
**Usage:** Connectors, agent connections

### Subscription
```typescript
interface Subscription {
  id: string
  organizationId: string
  plan: "node" | "control" | "command" | "enterprise"
  status: "active" | "past_due" | "canceled" | "trialing"
  billingCycle: "monthly" | "annual"
  currentPeriodStart: string
  currentPeriodEnd: string
  stripeCustomerId: string
  stripeSubscriptionId: string
  usage: {
    workflowRuns: { used: number, limit: number }
    teamMembers: { used: number, limit: number }
    storage: { used: number, limit: number }
  }
}
```
**Classification:** STRONGLY IMPLIED  
**Usage:** Billing, upgrade prompts, usage limits

---

## 7. API / BACKEND EXPECTATIONS (FRONTEND VIEW)

### Authentication APIs (CRITICAL - NOT BUILT)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `POST /api/auth/signup` | Create user account | CRITICAL | NOT BUILT |
| `POST /api/auth/login` | Authenticate user | CRITICAL | NOT BUILT |
| `POST /api/auth/logout` | End session | CRITICAL | NOT BUILT |
| `POST /api/auth/forgot-password` | Password reset | CRITICAL | NOT BUILT |
| `GET /api/auth/me` | Get current user | CRITICAL | NOT BUILT |

### Agent APIs (Partial Mock)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `GET /api/agents` | List agents | CRITICAL | MOCK EXISTS |
| `GET /api/agents/[id]` | Get agent detail | CRITICAL | NOT BUILT |
| `POST /api/agents` | Create agent | CRITICAL | NOT BUILT |
| `PUT /api/agents/[id]` | Update agent | HIGH | NOT BUILT |
| `DELETE /api/agents/[id]` | Delete agent | HIGH | NOT BUILT |
| `POST /api/agents/[id]/execute` | Execute agent task | CRITICAL | NOT BUILT |

### Workflow APIs (Partial Mock)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `GET /api/workflows` | List workflows | CRITICAL | MOCK EXISTS |
| `GET /api/workflows/[id]` | Get workflow detail | CRITICAL | NOT BUILT |
| `POST /api/workflows` | Create workflow | CRITICAL | NOT BUILT |
| `PUT /api/workflows/[id]` | Update workflow | HIGH | NOT BUILT |
| `DELETE /api/workflows/[id]` | Delete workflow | HIGH | NOT BUILT |
| `POST /api/workflows/[id]/execute` | Execute workflow | CRITICAL | NOT BUILT |
| `POST /api/workflows/[id]/schedule` | Set schedule | HIGH | NOT BUILT |

### Run APIs (Partial Mock)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `GET /api/runs` | List runs | CRITICAL | MOCK EXISTS |
| `GET /api/runs/[id]` | Get run detail | CRITICAL | NOT BUILT |
| `POST /api/runs/[id]/cancel` | Cancel run | HIGH | NOT BUILT |
| `POST /api/runs/[id]/retry` | Retry run | HIGH | NOT BUILT |

### Approval APIs (Partial Mock)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `GET /api/approvals` | List pending approvals | CRITICAL | MOCK EXISTS |
| `POST /api/approvals/[id]/approve` | Approve action | CRITICAL | NOT BUILT |
| `POST /api/approvals/[id]/reject` | Reject action | CRITICAL | NOT BUILT |

### AI/Operator APIs (NOT BUILT)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `POST /api/ai/chat` | AI chat completion | CRITICAL | NOT BUILT |
| `POST /api/ai/analyze` | Analyze task/issue | CRITICAL | NOT BUILT |
| `POST /api/ai/suggest-actions` | Get action suggestions | CRITICAL | NOT BUILT |
| `POST /api/ai/execute-action` | Execute AI action | CRITICAL | NOT BUILT |

### Integration/Connector APIs (NOT BUILT)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `GET /api/integrations` | List integrations | HIGH | NOT BUILT |
| `GET /api/integrations/[id]` | Get integration | HIGH | NOT BUILT |
| `POST /api/integrations/oauth/[provider]` | Start OAuth | HIGH | NOT BUILT |
| `DELETE /api/integrations/[id]` | Disconnect | HIGH | NOT BUILT |

### Billing APIs (NOT BUILT)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `GET /api/billing/subscription` | Get subscription | CRITICAL | NOT BUILT |
| `POST /api/billing/checkout` | Create checkout | CRITICAL | NOT BUILT |
| `POST /api/billing/portal` | Customer portal | HIGH | NOT BUILT |
| `POST /api/webhooks/stripe` | Stripe webhooks | CRITICAL | NOT BUILT |

### Settings APIs (NOT BUILT)

| Endpoint | Purpose | Priority | Status |
|----------|---------|----------|--------|
| `GET /api/settings` | Get settings | HIGH | NOT BUILT |
| `PUT /api/settings` | Update settings | HIGH | NOT BUILT |
| `GET /api/settings/api-keys` | List API keys | HIGH | NOT BUILT |
| `POST /api/settings/api-keys` | Create API key | HIGH | NOT BUILT |

---

## 8. STATE MANAGEMENT & UX CONDITIONS

### Required UI States

| State | Where Needed | Currently Supported | Launch Critical |
|-------|-------------|--------------------|-----------------| 
| Loading | All data pages | YES (skeleton components) | YES |
| Empty | Lists (agents, workflows, runs) | YES (empty state components) | YES |
| Error | API failures | PARTIAL (toast only) | YES |
| Success | Form submissions | YES (toast) | YES |
| Validation | All forms | PARTIAL | YES |
| Permissions | Admin vs Lite features | YES (view mode) | YES |
| Subscription gating | Premium features | PARTIAL (upgrade prompts) | YES |
| Real-time status | Runs, tasks | PLACEHOLDER | HIGH |
| Offline | Connectivity issues | NO | MEDIUM |

### Missing State Implementations

1. **API Error Boundaries** - No graceful error handling for failed fetches
2. **Optimistic Updates** - No optimistic UI for mutations
3. **Real-time Updates** - No WebSocket/SSE for live data
4. **Form State Persistence** - No draft saving
5. **Undo/Redo** - No undo for destructive actions

---

## 9. VERCEL DEPLOYMENT EXPECTATIONS

### Environment Variables Required

```env
# Authentication (NOT IMPLEMENTED YET)
NEXTAUTH_URL=
NEXTAUTH_SECRET=
# Or custom auth:
JWT_SECRET=
SESSION_SECRET=

# Database (NOT IMPLEMENTED YET)
DATABASE_URL=
# Recommended: Supabase, Neon, or PlanetScale

# AI Provider (NOT IMPLEMENTED YET)
OPENAI_API_KEY=
# Or Anthropic, etc.

# Stripe (NOT IMPLEMENTED YET)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=

# Integrations (NOT IMPLEMENTED YET)
SALESFORCE_CLIENT_ID=
SALESFORCE_CLIENT_SECRET=
HUBSPOT_CLIENT_ID=
HUBSPOT_CLIENT_SECRET=
# etc.
```

### API Routing Expectations
- All API routes under `/api/*`
- Currently 6 mock routes exist
- Expects standard REST conventions
- Should return JSON with consistent error format

### SSR vs CSR Assumptions
- Marketing pages: Can be static (SSG)
- App pages: Currently all client-side (`"use client"`)
- Could benefit from RSC for data fetching
- No streaming implemented

### Auth/Session Handling
- **NONE IMPLEMENTED**
- UI assumes authenticated throughout app
- Will need middleware for route protection
- Session must persist across tabs/refreshes

### What Will Break Without Backend

1. **Entire app** - No authentication means no real users
2. **AI Operator** - Core feature, completely placeholder
3. **Agents/Workflows** - No persistence, no execution
4. **Billing** - No subscription management
5. **Integrations** - No OAuth flows work
6. **Real-time updates** - No live status

---

## 10. GAPS / RISKS / FALSE ASSUMPTIONS

### Critical Gaps

1. **NO AUTHENTICATION** - The entire app assumes a logged-in state that doesn't exist. This is the #1 blocker.

2. **NO DATABASE** - All data is hardcoded or mock. Nothing persists.

3. **NO AI INTEGRATION** - The "AI Operator" is the core product but has no actual AI. The entire operator page is visual design only.

4. **NO EXECUTION ENGINE** - Workflows and agents cannot execute. No task queue, no job system.

5. **NO BILLING** - Stripe integration is placeholder. No actual payment processing.

### Decorative UI (Not Functional)

- AI Operator chat responses (hardcoded)
- Agent capability checkmarks (don't affect anything)
- Workflow node connections (visual only in builder)
- Metrics/analytics charts (static data)
- Real-time status indicators (static)
- Search functionality (no backend)

### Flows That Cannot Work

1. **User signup/login** - Auth not implemented
2. **Creating agents** - No persistence
3. **Building workflows** - No save/execute
4. **AI task execution** - No AI integration
5. **Tool connections** - No OAuth
6. **Payments** - No Stripe

### Conflicting Assumptions

- UI shows "12 systems connected" but no integration system exists
- Sidebar shows "v1.2.0" version but no versioning system exists
- Settings page has sections that imply features not built
- Onboarding flow promises connections that don't work

### Integration Risks

- The frontend expects specific response shapes from APIs
- No TypeScript types are shared with backend
- Error handling is minimal
- No API versioning strategy

---

## 11. FRONTEND → BACKEND HANDOFF (EXECUTION PLAN)

### Phase 1: Foundation (MUST BUILD FIRST)

1. **Database Setup**
   - Provision PostgreSQL (Supabase/Neon recommended)
   - Create schema for: Users, Organizations, Agents, Workflows, Runs
   - Set up migrations

2. **Authentication**
   - Implement auth (Supabase Auth recommended for speed)
   - Add middleware for route protection
   - Create `/api/auth/*` endpoints
   - Add session management

3. **Core CRUD APIs**
   - `GET/POST /api/agents`
   - `GET/POST /api/workflows`
   - `GET /api/runs`
   - Replace mock data with real database queries

### Phase 2: Core Features

4. **AI Integration**
   - Set up OpenAI/Anthropic integration
   - Create `/api/ai/chat` endpoint
   - Implement streaming responses
   - Add action suggestion logic

5. **Execution Engine**
   - Set up job queue (Vercel Cron, Inngest, or similar)
   - Implement workflow execution
   - Add run logging and status updates
   - Create approval system

6. **Billing (Stripe)**
   - Set up Stripe products/prices
   - Implement checkout flow
   - Add webhook handlers
   - Create subscription management

### Phase 3: Integrations

7. **OAuth Integrations**
   - Implement OAuth flows for key integrations
   - Store credentials securely
   - Create sync mechanisms

8. **Real-time Updates**
   - Add WebSocket/SSE for live status
   - Implement notification system
   - Add optimistic updates

### What Can Be Stubbed

- Secondary integrations (can add one at a time)
- Advanced analytics (can use static data initially)
- Team management (can be single-user first)
- Audit logs (can defer)
- Training system (can defer)

### What Must Be Real for Vercel Preview

- Authentication (users must log in)
- At least one API returning real data
- Basic agent/workflow CRUD
- Environment variables configured

### Contracts to Lock BEFORE Coding

1. **User/Organization schema** - Define exactly
2. **Agent schema** - Define capabilities system
3. **Workflow schema** - Define node types and configs
4. **API response format** - Standardize error handling
5. **AI response structure** - Define streaming format

---

## 12. JSON CONTRACT SUMMARY

```json
{
  "product_intent": "AI Operations Platform - SaaS for deploying and managing AI agents that automate business workflows",
  "pages": [
    { "path": "/", "type": "marketing", "status": "production-ready" },
    { "path": "/login", "type": "auth", "status": "partial" },
    { "path": "/operator", "type": "app", "status": "placeholder" },
    { "path": "/agents", "type": "app", "status": "partial" },
    { "path": "/workflows", "type": "app", "status": "partial" },
    { "path": "/runs", "type": "app", "status": "partial" },
    { "path": "/settings", "type": "app", "status": "partial" },
    { "path": "/settings/billing", "type": "app", "status": "placeholder" },
    { "path": "/lite", "type": "app", "status": "partial" }
  ],
  "components": [
    { "name": "AppShell", "status": "production-ready" },
    { "name": "Sidebar", "status": "production-ready" },
    { "name": "AICommandInput", "status": "partial" },
    { "name": "ModelSelector", "status": "production-ready" },
    { "name": "WorkflowBuilder", "status": "partial" }
  ],
  "flows": [
    { "name": "signup_to_first_value", "status": "broken", "blocker": "no auth" },
    { "name": "ai_operator_usage", "status": "placeholder", "blocker": "no AI" },
    { "name": "billing_subscription", "status": "placeholder", "blocker": "no Stripe" },
    { "name": "agent_creation", "status": "partial", "blocker": "no persistence" },
    { "name": "workflow_building", "status": "partial", "blocker": "no execution" }
  ],
  "data_contracts": [
    "User", "Organization", "Agent", "Workflow", "WorkflowNode", "Run", "RunLog", "Task", "Deliverable", "Integration", "Subscription"
  ],
  "api_requirements": [
    { "path": "/api/auth/*", "priority": "critical", "status": "not_built" },
    { "path": "/api/agents", "priority": "critical", "status": "mock_exists" },
    { "path": "/api/workflows", "priority": "critical", "status": "mock_exists" },
    { "path": "/api/ai/*", "priority": "critical", "status": "not_built" },
    { "path": "/api/billing/*", "priority": "critical", "status": "not_built" }
  ],
  "deployment_requirements": [
    "DATABASE_URL",
    "NEXTAUTH_SECRET or JWT_SECRET",
    "OPENAI_API_KEY",
    "STRIPE_SECRET_KEY"
  ],
  "critical_gaps": [
    "No authentication system",
    "No database - all data is mock",
    "No AI integration - core feature placeholder",
    "No execution engine for workflows/agents",
    "No billing/Stripe integration"
  ]
}
```

---

## FINAL NOTES

This frontend is **visually complete** but **functionally hollow**. The UI design and component architecture are production-ready, but every user-facing feature depends on backend systems that do not exist.

**Recommended approach:**
1. Do NOT deploy to production until auth is implemented
2. Start with Supabase for fastest path to working auth + database
3. Prioritize AI Operator since it's the core differentiator
4. Use feature flags to gradually enable functionality

**Estimated backend effort to reach MVP:**
- Auth + Database: 1-2 weeks
- Core CRUD APIs: 1 week
- AI Integration: 1-2 weeks
- Execution Engine: 2-3 weeks
- Billing: 1 week
- Integrations: 2+ weeks per integration

**Total to functional MVP: 8-12 weeks of backend work**

---

*Document prepared by Frontend Lead for Backend Handoff*
