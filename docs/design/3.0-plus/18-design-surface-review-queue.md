# Design surface review queue

Generated with `python3 scripts/inventory-design-surfaces.py`.

This inventory discovers routes and reachable local JSX controls/disclosures, including ancestor layouts, templates and loading/error/not-found boundaries composed by Next. Counts are source occurrences, not rendered buttons. Shared chrome can be reachable from many routes. Dynamic conditions, permissions, runtime tabs, computed imports and backend authorization require manual review. Family assignments are a starting hypothesis, especially for mixed discovery/setup routes.

**Visual acceptance: NOT RUN.** A listed file is not an accepted surface. Read each route and its reachable UI, then record browser evidence at 1440 / 834 / 390 including empty, error, loading, selected, pending and permission states.

Discovered 176 page routes and 366 reachable files containing controls or disclosures.

| Route | Level | Scope | Proposed family | Redirect expression | UI files | Source |
|---|---|---|---|---|---:|---|
| /about | Primary | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/about/page.tsx |
| /api | Primary | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/api/page.tsx |
| /blog/[slug] | Secondary/nested | Public/auth/support — classify | Review | — | 60 | apps/web/app/(marketing)/blog/[slug]/page.tsx |
| /blog | Primary | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/blog/page.tsx |
| /careers | Primary | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/careers/page.tsx |
| /changelog | Primary | Public/auth/support — classify | Review | — | 60 | apps/web/app/(marketing)/changelog/page.tsx |
| /contact | Primary | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/contact/page.tsx |
| /docs/[...slug] | Secondary/nested | Public/auth/support — classify | Review | — | 62 | apps/web/app/(marketing)/docs/[...slug]/page.tsx |
| /docs/api/swagger | Secondary/nested | Public/auth/support — classify | Review | — | 58 | apps/web/app/(marketing)/docs/api/swagger/page.tsx |
| /docs/faq | Secondary/nested | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/docs/faq/page.tsx |
| /docs/integrations | Secondary/nested | Public/auth/support — classify | Review | — | 67 | apps/web/app/(marketing)/docs/integrations/page.tsx |
| /docs | Primary | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/docs/page.tsx |
| /download | Primary | Public/auth/support — classify | Review | — | 60 | apps/web/app/(marketing)/download/page.tsx |
| /features/extension | Secondary/nested | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/features/extension/page.tsx |
| /features/marketplace | Secondary/nested | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/features/marketplace/page.tsx |
| /features | Primary | Public/auth/support — classify | Review | — | 68 | apps/web/app/(marketing)/features/page.tsx |
| /features/technology | Secondary/nested | Public/auth/support — classify | Review | — | 67 | apps/web/app/(marketing)/features/technology/page.tsx |
| /forgot-password | Primary | Public/auth/support — classify | Review | — | 60 | apps/web/app/(marketing)/forgot-password/page.tsx |
| /get-started | Primary | Public/auth/support — classify | Review | — | 59 | apps/web/app/(marketing)/get-started/page.tsx |
| /guides | Primary | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/guides/page.tsx |
| /login | Primary | Public/auth/support — classify | Review | — | 59 | apps/web/app/(marketing)/login/page.tsx |
| / | Primary | Public/auth/support — classify | Review | — | 64 | apps/web/app/(marketing)/page.tsx |
| /pricing | Primary | Public/auth/support — classify | Review | — | 71 | apps/web/app/(marketing)/pricing/page.tsx |
| /privacy | Primary | Public/auth/support — classify | Review | — | 60 | apps/web/app/(marketing)/privacy/page.tsx |
| /roadmap | Primary | Public/auth/support — classify | Review | — | 60 | apps/web/app/(marketing)/roadmap/page.tsx |
| /security | Primary | Public/auth/support — classify | Review | — | 67 | apps/web/app/(marketing)/security/page.tsx |
| /support | Primary | Public/auth/support — classify | Review | — | 61 | apps/web/app/(marketing)/support/page.tsx |
| /terms | Primary | Public/auth/support — classify | Review | — | 60 | apps/web/app/(marketing)/terms/page.tsx |
| /activity | Primary | Product | Operate | — | 70 | apps/web/app/activity/page.tsx |
| /admin/intelligence | Secondary/nested | Product | Manage | — | 81 | apps/web/app/admin/intelligence/page.tsx |
| /agents/[id]/capabilities | Secondary/nested | Product | Manage | — | 65 | apps/web/app/agents/[id]/capabilities/page.tsx |
| /agents/[id]/chat | Secondary/nested | Product | Manage | — | 64 | apps/web/app/agents/[id]/chat/page.tsx |
| /agents/[id]/knowledge | Secondary/nested | Product | Manage | — | 68 | apps/web/app/agents/[id]/knowledge/page.tsx |
| /agents/[id]/memory | Secondary/nested | Product | Manage | — | 65 | apps/web/app/agents/[id]/memory/page.tsx |
| /agents/[id] | Secondary/nested | Product | Manage | — | 73 | apps/web/app/agents/[id]/page.tsx |
| /agents/new | Secondary/nested | Product | Create | — | 70 | apps/web/app/agents/new/page.tsx |
| /agents | Primary | Product | Manage | — | 77 | apps/web/app/agents/page.tsx |
| /agents/swarm | Secondary/nested | Product | Manage | — | 52 | apps/web/app/agents/swarm/page.tsx |
| /ai/help/control | Secondary/nested | Product | Create | — | 64 | apps/web/app/ai/help/control/page.tsx |
| /ai | Primary | Product | Create | — | 63 | apps/web/app/ai/page.tsx |
| /approvals | Primary | Product | Operate | — | 67 | apps/web/app/approvals/page.tsx |
| /assignments/[id] | Secondary/nested | Product | Operate | — | 66 | apps/web/app/assignments/[id]/page.tsx |
| /assignments/new | Secondary/nested | Product | Create | — | 64 | apps/web/app/assignments/new/page.tsx |
| /assignments | Primary | Product | Operate | — | 67 | apps/web/app/assignments/page.tsx |
| /assistant | Primary | Product | Create | — | 52 | apps/web/app/assistant/page.tsx |
| /audit | Primary | Product | Operate | — | 65 | apps/web/app/audit/page.tsx |
| /auth/callback/complete | Secondary/nested | Public/auth/support — classify | Review | — | 53 | apps/web/app/auth/callback/complete/page.tsx |
| /chat | Primary | Product | Create | — | 64 | apps/web/app/chat/page.tsx |
| /connectors/[id] | Secondary/nested | Product | Manage | — | 67 | apps/web/app/connectors/[id]/page.tsx |
| /connectors | Primary | Product | Manage | — | 70 | apps/web/app/connectors/page.tsx |
| /deck | Primary | Public/auth/support — classify | Review | — | 53 | apps/web/app/deck/page.tsx |
| /deliverables | Primary | Product | Operate | /lite/deliverables | 52 | apps/web/app/deliverables/page.tsx |
| /desktop/connect | Secondary/nested | Product | Manage | — | 53 | apps/web/app/desktop/connect/page.tsx |
| /dev/ai-workspace-preview | Secondary/nested | Fixture/development | Review | — | 71 | apps/web/app/dev/ai-workspace-preview/page.tsx |
| /dev/carbon-board | Secondary/nested | Fixture/development | Review | — | 56 | apps/web/app/dev/carbon-board/page.tsx |
| /dev/slice-0-foundation | Secondary/nested | Fixture/development | Review | — | 55 | apps/web/app/dev/slice-0-foundation/page.tsx |
| /dev/slice-1-workspace | Secondary/nested | Fixture/development | Review | — | 53 | apps/web/app/dev/slice-1-workspace/page.tsx |
| /e2e/chat-progress | Secondary/nested | Fixture/development | Review | — | 52 | apps/web/app/e2e/chat-progress/page.tsx |
| /e2e/execution-result | Secondary/nested | Fixture/development | Review | — | 52 | apps/web/app/e2e/execution-result/page.tsx |
| /e2e/shot-upload | Secondary/nested | Fixture/development | Review | — | 53 | apps/web/app/e2e/shot-upload/page.tsx |
| /e2e/shots/activity | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/activity/page.tsx |
| /e2e/shots/agent-chat | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/agent-chat/page.tsx |
| /e2e/shots/agent-detail | Secondary/nested | Fixture/development | Review | — | 73 | apps/web/app/e2e/shots/agent-detail/page.tsx |
| /e2e/shots/agent-knowledge | Secondary/nested | Fixture/development | Review | — | 66 | apps/web/app/e2e/shots/agent-knowledge/page.tsx |
| /e2e/shots/agents | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/agents/page.tsx |
| /e2e/shots/agents-4 | Secondary/nested | Fixture/development | Review | — | 71 | apps/web/app/e2e/shots/agents-4/page.tsx |
| /e2e/shots/ai | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/ai/page.tsx |
| /e2e/shots/approvals | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/approvals/page.tsx |
| /e2e/shots/assignments | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/assignments/page.tsx |
| /e2e/shots/avatar-states | Secondary/nested | Fixture/development | Review | — | 52 | apps/web/app/e2e/shots/avatar-states/page.tsx |
| /e2e/shots/billing-states | Secondary/nested | Fixture/development | Review | — | 65 | apps/web/app/e2e/shots/billing-states/page.tsx |
| /e2e/shots/builder | Secondary/nested | Fixture/development | Create | — | 70 | apps/web/app/e2e/shots/builder/page.tsx |
| /e2e/shots/connectors | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/connectors/page.tsx |
| /e2e/shots/home | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/home/page.tsx |
| /e2e/shots/intelligence | Secondary/nested | Fixture/development | Review | — | 64 | apps/web/app/e2e/shots/intelligence/page.tsx |
| /e2e/shots/intelligence-field | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/intelligence-field/page.tsx |
| /e2e/shots/learning-4 | Secondary/nested | Fixture/development | Review | — | 70 | apps/web/app/e2e/shots/learning-4/page.tsx |
| /e2e/shots/marketplace | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/marketplace/page.tsx |
| /e2e/shots/marketplace-installed | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/marketplace-installed/page.tsx |
| /e2e/shots/marketplace-pack/[slug] | Secondary/nested | Fixture/development | Review | — | 71 | apps/web/app/e2e/shots/marketplace-pack/[slug]/page.tsx |
| /e2e/shots/metrics | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/metrics/page.tsx |
| /e2e/shots/outcome-states | Secondary/nested | Fixture/development | Review | — | 52 | apps/web/app/e2e/shots/outcome-states/page.tsx |
| /e2e/shots/proof | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/proof/page.tsx |
| /e2e/shots/relationships | Secondary/nested | Fixture/development | Review | — | 70 | apps/web/app/e2e/shots/relationships/page.tsx |
| /e2e/shots/sources | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/sources/page.tsx |
| /e2e/shots/voice-states | Secondary/nested | Fixture/development | Review | — | 55 | apps/web/app/e2e/shots/voice-states/page.tsx |
| /e2e/shots/workflows | Secondary/nested | Fixture/development | Review | — | 128 | apps/web/app/e2e/shots/workflows/page.tsx |
| /e2e/task-side-panel | Secondary/nested | Fixture/development | Review | — | 52 | apps/web/app/e2e/task-side-panel/page.tsx |
| /e2e/voice-duplex | Secondary/nested | Fixture/development | Review | — | 53 | apps/web/app/e2e/voice-duplex/page.tsx |
| /environments | Primary | Product | Manage | — | 64 | apps/web/app/environments/page.tsx |
| /extension/connect | Secondary/nested | Product | Manage | — | 53 | apps/web/app/extension/connect/page.tsx |
| /goals/[id] | Secondary/nested | Product | Operate | — | 64 | apps/web/app/goals/[id]/page.tsx |
| /goals | Primary | Product | Operate | — | 65 | apps/web/app/goals/page.tsx |
| /home | Primary | Product | Operate | — | 68 | apps/web/app/home/page.tsx |
| /integrations/[id] | Secondary/nested | Product | Manage | — | 64 | apps/web/app/integrations/[id]/page.tsx |
| /integrations/new | Secondary/nested | Product | Create | — | 64 | apps/web/app/integrations/new/page.tsx |
| /integrations | Primary | Product | Manage | /connectors | 52 | apps/web/app/integrations/page.tsx |
| /intelligence/agents/[id] | Secondary/nested | Product | Understand | — | 63 | apps/web/app/intelligence/agents/[id]/page.tsx |
| /intelligence/agents | Secondary/nested | Product | Understand | — | 63 | apps/web/app/intelligence/agents/page.tsx |
| /intelligence/learning | Secondary/nested | Product | Understand | — | 81 | apps/web/app/intelligence/learning/page.tsx |
| /intelligence/memory | Secondary/nested | Product | Understand | — | 65 | apps/web/app/intelligence/memory/page.tsx |
| /intelligence/model-studio | Secondary/nested | Product | Create | — | 73 | apps/web/app/intelligence/model-studio/page.tsx |
| /intelligence/models/[name] | Secondary/nested | Product | Understand | — | 64 | apps/web/app/intelligence/models/[name]/page.tsx |
| /intelligence/models | Secondary/nested | Product | Understand | — | 71 | apps/web/app/intelligence/models/page.tsx |
| /intelligence | Primary | Product | Understand | — | 82 | apps/web/app/intelligence/page.tsx |
| /intelligence/performance | Secondary/nested | Product | Understand | — | 74 | apps/web/app/intelligence/performance/page.tsx |
| /intelligence/predictive | Secondary/nested | Product | Understand | — | 72 | apps/web/app/intelligence/predictive/page.tsx |
| /intelligence/reports | Secondary/nested | Product | Understand | — | 74 | apps/web/app/intelligence/reports/page.tsx |
| /lite/assign | Secondary/nested | Product | Operate | — | 64 | apps/web/app/lite/assign/page.tsx |
| /lite/deliverables | Secondary/nested | Product | Operate | — | 64 | apps/web/app/lite/deliverables/page.tsx |
| /lite | Primary | Product | Operate | — | 52 | apps/web/app/lite/page.tsx |
| /lite/results | Secondary/nested | Product | Understand | — | 64 | apps/web/app/lite/results/page.tsx |
| /lite/tasks | Secondary/nested | Product | Operate | — | 65 | apps/web/app/lite/tasks/page.tsx |
| /marketplace/admin | Secondary/nested | Product | Manage | — | 64 | apps/web/app/marketplace/admin/page.tsx |
| /marketplace/analytics | Secondary/nested | Product | Understand | — | 64 | apps/web/app/marketplace/analytics/page.tsx |
| /marketplace/analytics/roi | Secondary/nested | Product | Understand | — | 52 | apps/web/app/marketplace/analytics/roi/page.tsx |
| /marketplace/assets/[slug] | Secondary/nested | Product | Discover | — | 71 | apps/web/app/marketplace/assets/[slug]/page.tsx |
| /marketplace/assets | Secondary/nested | Product | Discover | — | 72 | apps/web/app/marketplace/assets/page.tsx |
| /marketplace/billing | Secondary/nested | Product | Create | — | 64 | apps/web/app/marketplace/billing/page.tsx |
| /marketplace/capabilities | Secondary/nested | Product | Discover | — | 65 | apps/web/app/marketplace/capabilities/page.tsx |
| /marketplace/connectors | Secondary/nested | Product | Discover | — | 64 | apps/web/app/marketplace/connectors/page.tsx |
| /marketplace/installed | Secondary/nested | Product | Manage | — | 66 | apps/web/app/marketplace/installed/page.tsx |
| /marketplace/org/assets/new | Secondary/nested | Product | Create | — | 64 | apps/web/app/marketplace/org/assets/new/page.tsx |
| /marketplace/org | Secondary/nested | Product | Discover | — | 64 | apps/web/app/marketplace/org/page.tsx |
| /marketplace/org-admin | Secondary/nested | Product | Manage | — | 68 | apps/web/app/marketplace/org-admin/page.tsx |
| /marketplace/platform-admin | Secondary/nested | Product | Manage | — | 66 | apps/web/app/marketplace/platform-admin/page.tsx |
| /marketplace/private | Secondary/nested | Product | Discover | — | 64 | apps/web/app/marketplace/private/page.tsx |
| /marketplace/publisher/analytics | Secondary/nested | Product | Understand | — | 64 | apps/web/app/marketplace/publisher/analytics/page.tsx |
| /marketplace/publisher | Secondary/nested | Product | Manage | — | 64 | apps/web/app/marketplace/publisher/page.tsx |
| /marketplace/role-packs | Secondary/nested | Product | Discover | /marketplace/assets?type=department_pack | 52 | apps/web/app/marketplace/role-packs/page.tsx |
| /marketplace/sandbox | Secondary/nested | Product | Create | — | 65 | apps/web/app/marketplace/sandbox/page.tsx |
| /marketplace/saved | Secondary/nested | Product | Discover | — | 65 | apps/web/app/marketplace/saved/page.tsx |
| /marketplace/submit | Secondary/nested | Product | Create | — | 64 | apps/web/app/marketplace/submit/page.tsx |
| /metrics | Primary | Product | Understand | — | 64 | apps/web/app/metrics/page.tsx |
| /models/[id] | Secondary/nested | Product | Manage | — | 65 | apps/web/app/models/[id]/page.tsx |
| /models/built-in/[name] | Secondary/nested | Product | Manage | — | 64 | apps/web/app/models/built-in/[name]/page.tsx |
| /models/built-in | Secondary/nested | Product | Manage | — | 71 | apps/web/app/models/built-in/page.tsx |
| /models | Primary | Product | Manage | — | 75 | apps/web/app/models/page.tsx |
| /multi-agent-run | Primary | Product | Operate | — | 67 | apps/web/app/multi-agent-run/page.tsx |
| /notifications | Primary | Product | Operate | — | 64 | apps/web/app/notifications/page.tsx |
| /onboarding | Primary | Product | Create | — | 52 | apps/web/app/onboarding/page.tsx |
| /operator | Primary | Product | Manage | — | 52 | apps/web/app/operator/page.tsx |
| /outcomes | Primary | Product | Understand | — | 52 | apps/web/app/outcomes/page.tsx |
| / | Primary | Public/auth/support — classify | Review | — | 63 | apps/web/app/page.tsx |
| /platform/cs-workspace | Secondary/nested | Product | Manage | — | 64 | apps/web/app/platform/cs-workspace/page.tsx |
| /plays/[key] | Secondary/nested | Product | Discover | — | 67 | apps/web/app/plays/[key]/page.tsx |
| /plays/[key]/results/[outcomeId] | Secondary/nested | Product | Understand | — | 64 | apps/web/app/plays/[key]/results/[outcomeId]/page.tsx |
| /plays | Primary | Product | Discover | — | 64 | apps/web/app/plays/page.tsx |
| /runs/[id] | Secondary/nested | Product | Operate | — | 67 | apps/web/app/runs/[id]/page.tsx |
| /runs | Primary | Product | Operate | — | 52 | apps/web/app/runs/page.tsx |
| /schedules | Primary | Product | Operate | — | 73 | apps/web/app/schedules/page.tsx |
| /search | Primary | Product | Discover | — | 64 | apps/web/app/search/page.tsx |
| /settings/approvals | Secondary/nested | Product | Create | — | 65 | apps/web/app/settings/approvals/page.tsx |
| /settings/billing/checkout | Secondary/nested | Product | Create | — | 64 | apps/web/app/settings/billing/checkout/page.tsx |
| /settings/billing | Secondary/nested | Product | Create | — | 65 | apps/web/app/settings/billing/page.tsx |
| /settings/billing-usage | Secondary/nested | Product | Create | /settings/billing | 52 | apps/web/app/settings/billing-usage/page.tsx |
| /settings/enterprise | Secondary/nested | Product | Create | — | 74 | apps/web/app/settings/enterprise/page.tsx |
| /settings/federation | Secondary/nested | Product | Create | — | 73 | apps/web/app/settings/federation/page.tsx |
| /settings/organizations | Secondary/nested | Product | Create | — | 65 | apps/web/app/settings/organizations/page.tsx |
| /settings | Primary | Product | Create | — | 72 | apps/web/app/settings/page.tsx |
| /settings/profile | Secondary/nested | Product | Create | — | 65 | apps/web/app/settings/profile/page.tsx |
| /settings/team/permissions | Secondary/nested | Product | Create | — | 65 | apps/web/app/settings/team/permissions/page.tsx |
| /sources/[id]/agents | Secondary/nested | Product | Manage | — | 64 | apps/web/app/sources/[id]/agents/page.tsx |
| /sources/[id] | Secondary/nested | Product | Manage | — | 65 | apps/web/app/sources/[id]/page.tsx |
| /sources | Primary | Product | Manage | — | 68 | apps/web/app/sources/page.tsx |
| /systems | Primary | Product | Manage | — | 52 | apps/web/app/systems/page.tsx |
| /tasks | Primary | Product | Operate | — | 52 | apps/web/app/tasks/page.tsx |
| /training | Primary | Product | Create | — | 66 | apps/web/app/training/page.tsx |
| /welcome | Primary | Product | Create | — | 54 | apps/web/app/welcome/page.tsx |
| /workflows/[id]/builder | Secondary/nested | Product | Create | — | 70 | apps/web/app/workflows/[id]/builder/page.tsx |
| /workflows/[id] | Secondary/nested | Product | Operate | — | 68 | apps/web/app/workflows/[id]/page.tsx |
| /workflows/[id]/schedules | Secondary/nested | Product | Operate | — | 72 | apps/web/app/workflows/[id]/schedules/page.tsx |
| /workflows/failure-predictions | Secondary/nested | Product | Operate | — | 52 | apps/web/app/workflows/failure-predictions/page.tsx |
| /workflows/new/builder | Secondary/nested | Product | Create | — | 64 | apps/web/app/workflows/new/builder/page.tsx |
| /workflows/new | Secondary/nested | Product | Create | — | 52 | apps/web/app/workflows/new/page.tsx |
| /workflows | Primary | Product | Operate | — | 72 | apps/web/app/workflows/page.tsx |

## Tertiary disclosures and control sources

Use this index to follow windows, inspectors, popovers, dialogs and action controls beyond the page level. Full JSX lists include primitive wrappers; opening a wrapper does not establish a functional or visible surface.

| Source | Disclosure components | Control occurrences | Reachable routes |
|---|---|---:|---:|
| apps/web/app/(marketing)/about/page.tsx | — | 2 | 1 |
| apps/web/app/(marketing)/api/page.tsx | — | 1 | 1 |
| apps/web/app/(marketing)/blog/blog-page-client.tsx | — | 1 | 1 |
| apps/web/app/(marketing)/careers/page.tsx | — | 2 | 1 |
| apps/web/app/(marketing)/contact/page.tsx | — | 5 | 1 |
| apps/web/app/(marketing)/error.tsx | — | 2 | 28 |
| apps/web/app/(marketing)/forgot-password/page.tsx | — | 3 | 1 |
| apps/web/app/(marketing)/get-started/page.tsx | — | 6 | 1 |
| apps/web/app/(marketing)/guides/page.tsx | — | 1 | 1 |
| apps/web/app/(marketing)/login/page.tsx | — | 4 | 1 |
| apps/web/app/(marketing)/pricing/page.tsx | — | 3 | 1 |
| apps/web/app/(marketing)/support/page.tsx | — | 1 | 1 |
| apps/web/app/activity/page.tsx | — | 13 | 16 |
| apps/web/app/admin/intelligence/_components/chat-persona-settings-card.tsx | — | 2 | 1 |
| apps/web/app/admin/intelligence/_components/cognitive-turns-tab.tsx | — | 5 | 1 |
| apps/web/app/admin/intelligence/_components/engine-settings-tab.tsx | — | 6 | 1 |
| apps/web/app/admin/intelligence/_components/evaluation-tab.tsx | — | 4 | 1 |
| apps/web/app/admin/intelligence/_components/knowledge-fabric-quality-card.tsx | — | 5 | 1 |
| apps/web/app/admin/intelligence/_components/memory-promotion-tab.tsx | — | 6 | 1 |
| apps/web/app/admin/intelligence/_components/org-learning-models-card.tsx | — | 2 | 1 |
| apps/web/app/admin/intelligence/_components/outcomes-tab.tsx | — | 2 | 1 |
| apps/web/app/admin/intelligence/_components/performance-tab.tsx | — | 1 | 1 |
| apps/web/app/admin/intelligence/page.tsx | — | 2 | 1 |
| apps/web/app/agents/[id]/capabilities/page.tsx | — | 2 | 1 |
| apps/web/app/agents/[id]/chat/page.tsx | — | 1 | 16 |
| apps/web/app/agents/[id]/knowledge/page.tsx | AgentKnowledgeAddSheet, AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle | 6 | 1 |
| apps/web/app/agents/[id]/memory/page.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, Dialog, MemoryEditorDialog | 12 | 1 |
| apps/web/app/agents/[id]/page.tsx | — | 7 | 2 |
| apps/web/app/agents/new/page.tsx | — | 10 | 1 |
| apps/web/app/agents/page.tsx | AgentFleetInspectorBody, AgentPreviewSheet, Sheet | 9 | 16 |
| apps/web/app/ai/_components/ai-execute-results.tsx | — | 1 | 175 |
| apps/web/app/ai/_components/ai-find-results.tsx | — | 1 | 175 |
| apps/web/app/ai/_components/ai-landing.tsx | — | 1 | 175 |
| apps/web/app/ai/_components/ai-mobile-sheet-bridge.tsx | GravitreAIMobileSheet | 1 | 175 |
| apps/web/app/ai/_components/ai-starting-state.tsx | — | 1 | 175 |
| apps/web/app/ai/_components/ai-voice-agent-picker.tsx | DropdownMenu | 3 | 175 |
| apps/web/app/ai/_components/ai-workspace.tsx | ChatModality, ChatWindowControls, ConnectedFilePickerDialog, DropdownMenu, GravitreAIMobileSheetBridge, VoiceMicSettingsPopover | 9 | 175 |
| apps/web/app/ai/_components/connected-file-picker-dialog.tsx | Dialog | 8 | 175 |
| apps/web/app/ai/_components/live-activity-rail.tsx | — | 2 | 175 |
| apps/web/app/ai/help/control/page.tsx | — | 3 | 1 |
| apps/web/app/approvals/page.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle | 7 | 16 |
| apps/web/app/assignments/[id]/page.tsx | AssignmentApprovalDialog, Dialog, SelectionInspector | 9 | 1 |
| apps/web/app/assignments/page.tsx | MissionInspector, NewAssignmentModal | 6 | 16 |
| apps/web/app/audit/page.tsx | — | 12 | 1 |
| apps/web/app/auth/callback/complete/page.tsx | — | 1 | 1 |
| apps/web/app/chat/page.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle | 8 | 2 |
| apps/web/app/connectors/[id]/page.tsx | Dialog, DropdownMenu | 17 | 1 |
| apps/web/app/connectors/page.tsx | AddConnectorModal, ConfigureModal, DeleteModal, Dialog, DropdownMenu, GaPropertyPickerModal, GoogleAdsCustomerPickerModal, GscSitePickerModal, ResponsiveConnectorInspector | 94 | 16 |
| apps/web/app/deck/deck-stage.tsx | — | 4 | 1 |
| apps/web/app/desktop/connect/page.tsx | — | 2 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/design-exploration-shell.tsx | — | 3 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/selected-ai.tsx | — | 1 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/activity-trace-prototype.tsx | — | 8 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/agent-workspace-concepts-prototype.tsx | — | 3 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/dashboard-concepts-prototype.tsx | — | 6 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/design-selection-index.tsx | — | 5 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/g-struct-decision-package.tsx | — | 2 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/intelligence-field-prototype.tsx | — | 9 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/intelligence-journey-prototype.tsx | — | 11 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/model-studio-prototype.tsx | — | 5 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/nav-rail-prototype.tsx | — | 3 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/page-intro-variants-prototype.tsx | — | 11 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/saasframe-research-trace.tsx | — | 3 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/shared-ai-workspace-prototype.tsx | — | 5 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/window-manager-docked-prototype.tsx | — | 6 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/workflow-builder-rf-prototype.tsx | — | 3 | 1 |
| apps/web/app/dev/ai-workspace-preview/_components/ux30-plus/workflow-gen-preview-prototype.tsx | — | 4 | 1 |
| apps/web/app/dev/carbon-board/_components/ai-native-board.tsx | — | 1 | 1 |
| apps/web/app/dev/carbon-board/_components/carbon-board.tsx | BuilderInspector | 9 | 1 |
| apps/web/app/dev/slice-0-foundation/_components/slice-0-foundation-preview.tsx | GravitreWindowManagerShell | 7 | 1 |
| apps/web/app/dev/slice-1-workspace/_components/slice-1-workspace-preview.tsx | GravitreAIMobileSheetBridge, GravitreInspector, GravitreInspectorFields, GravitreInspectorKind, GravitreInspectorNotice, GravitreInspectorSection | 5 | 1 |
| apps/web/app/e2e/shot-upload/page.tsx | — | 1 | 1 |
| apps/web/app/e2e/shots/_components/ai-workspace-proof-page.tsx | — | 1 | 15 |
| apps/web/app/e2e/shots/voice-states/page.tsx | — | 2 | 1 |
| apps/web/app/e2e/voice-duplex/harness.tsx | — | 1 | 1 |
| apps/web/app/environments/page.tsx | DropdownMenu | 8 | 1 |
| apps/web/app/extension/connect/page.tsx | — | 2 | 1 |
| apps/web/app/global-error.tsx | — | 1 | 175 |
| apps/web/app/goals/[id]/page.tsx | — | 1 | 1 |
| apps/web/app/goals/page.tsx | — | 7 | 1 |
| apps/web/app/integrations/[id]/page.tsx | — | 6 | 1 |
| apps/web/app/integrations/new/page.tsx | — | 10 | 1 |
| apps/web/app/intelligence/learning/page.tsx | — | 1 | 1 |
| apps/web/app/intelligence/memory/page.tsx | — | 4 | 1 |
| apps/web/app/intelligence/models/[name]/page.tsx | — | 8 | 2 |
| apps/web/app/intelligence/page.tsx | — | 2 | 16 |
| apps/web/app/intelligence/performance/page.tsx | — | 1 | 1 |
| apps/web/app/intelligence/predictive/page.tsx | — | 1 | 1 |
| apps/web/app/intelligence/reports/page.tsx | — | 1 | 1 |
| apps/web/app/lite/assign/page.tsx | — | 3 | 1 |
| apps/web/app/lite/deliverables/page.tsx | — | 1 | 1 |
| apps/web/app/lite/tasks/page.tsx | — | 3 | 1 |
| apps/web/app/marketplace/admin/page.tsx | Dialog | 12 | 1 |
| apps/web/app/marketplace/analytics/page.tsx | — | 2 | 1 |
| apps/web/app/marketplace/assets/[slug]/page.tsx | DropdownMenu, InstallStepperSheet, MarketplaceDecisionDialog | 11 | 2 |
| apps/web/app/marketplace/assets/page.tsx | InstallStepperSheet | 14 | 16 |
| apps/web/app/marketplace/billing/page.tsx | — | 9 | 1 |
| apps/web/app/marketplace/capabilities/page.tsx | WorkDecisionDialog | 43 | 1 |
| apps/web/app/marketplace/connectors/page.tsx | — | 5 | 1 |
| apps/web/app/marketplace/installed/page.tsx | Dialog, InstalledInspector, Sheet | 10 | 16 |
| apps/web/app/marketplace/org-admin/page.tsx | Dialog, MarketplaceDecisionDialog | 12 | 1 |
| apps/web/app/marketplace/org/assets/new/page.tsx | — | 13 | 1 |
| apps/web/app/marketplace/org/page.tsx | — | 2 | 1 |
| apps/web/app/marketplace/platform-admin/page.tsx | Dialog, MarketplaceDecisionDialog | 10 | 1 |
| apps/web/app/marketplace/private/page.tsx | — | 9 | 1 |
| apps/web/app/marketplace/publisher/analytics/page.tsx | — | 6 | 1 |
| apps/web/app/marketplace/publisher/page.tsx | — | 10 | 1 |
| apps/web/app/marketplace/sandbox/page.tsx | MarketplaceDecisionDialog | 6 | 1 |
| apps/web/app/marketplace/saved/page.tsx | — | 3 | 1 |
| apps/web/app/marketplace/submit/page.tsx | — | 6 | 1 |
| apps/web/app/metrics/page.tsx | DropdownMenu | 6 | 16 |
| apps/web/app/models/[id]/page.tsx | — | 3 | 1 |
| apps/web/app/models/page.tsx | Dialog | 12 | 1 |
| apps/web/app/multi-agent-run/page.tsx | SelectionInspector, StartSwarmDialog | 4 | 1 |
| apps/web/app/notifications/page.tsx | — | 8 | 1 |
| apps/web/app/platform/cs-workspace/page.tsx | DropdownMenu | 15 | 1 |
| apps/web/app/plays/[key]/page.tsx | — | 4 | 1 |
| apps/web/app/plays/[key]/results/[outcomeId]/page.tsx | — | 1 | 1 |
| apps/web/app/plays/page.tsx | — | 2 | 1 |
| apps/web/app/runs/[id]/page.tsx | — | 15 | 1 |
| apps/web/app/schedules/_components/calendar-view.tsx | — | 1 | 2 |
| apps/web/app/schedules/_components/day-view.tsx | — | 1 | 2 |
| apps/web/app/schedules/_components/gantt-view.tsx | — | 1 | 2 |
| apps/web/app/schedules/_components/list-view.tsx | — | 1 | 2 |
| apps/web/app/schedules/_components/mobile-agenda.tsx | — | 4 | 2 |
| apps/web/app/schedules/_components/schedule-item-dialog.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, ScheduleEditorDialog | 6 | 2 |
| apps/web/app/schedules/_components/schedules-view.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, ScheduleItemDialog | 7 | 2 |
| apps/web/app/schedules/page.tsx | ScheduleEditorDialog | 2 | 1 |
| apps/web/app/settings/approvals/page.tsx | — | 8 | 1 |
| apps/web/app/settings/billing/checkout/page.tsx | — | 4 | 1 |
| apps/web/app/settings/billing/page.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, Dialog | 30 | 2 |
| apps/web/app/settings/enterprise/page.tsx | — | 1 | 1 |
| apps/web/app/settings/federation/page.tsx | CreateDelegatedTaskDialog, CreateHandoffDialog, InvitePartnerDialog, ProposeGrantDialog | 7 | 1 |
| apps/web/app/settings/organizations/page.tsx | Dialog | 20 | 1 |
| apps/web/app/settings/page.tsx | — | 20 | 1 |
| apps/web/app/settings/profile/page.tsx | Dialog | 17 | 1 |
| apps/web/app/settings/team/permissions/page.tsx | — | 2 | 1 |
| apps/web/app/sources/[id]/agents/page.tsx | — | 1 | 1 |
| apps/web/app/sources/[id]/page.tsx | Dialog | 9 | 1 |
| apps/web/app/sources/page.tsx | AddDataSourceModal, Sheet, SourceInspector | 8 | 16 |
| apps/web/app/training/page.tsx | Dialog | 47 | 1 |
| apps/web/app/welcome/page.tsx | — | 11 | 1 |
| apps/web/app/workflows/[id]/builder/page.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, BuilderInspector, DebateViewDialog, Dialog, DropdownMenu, ScheduleEditorDialog, Sheet, WorkflowIntelligenceDrawer | 91 | 2 |
| apps/web/app/workflows/[id]/page.tsx | WorkDecisionDialog | 11 | 1 |
| apps/web/app/workflows/[id]/schedules/page.tsx | ScheduleEditorDialog | 2 | 1 |
| apps/web/app/workflows/new/builder/page.tsx | — | 5 | 1 |
| apps/web/app/workflows/page.tsx | DropdownMenu | 9 | 16 |
| apps/web/components/activity/activity-trace-panel.tsx | — | 5 | 16 |
| apps/web/components/agent-swarm/start-swarm-dialog.tsx | Dialog | 11 | 1 |
| apps/web/components/agent-swarm/swarm-run-detail-panel.tsx | — | 6 | 1 |
| apps/web/components/agents/agent-knowledge-packs-editor.tsx | — | 1 | 1 |
| apps/web/components/agents/agent-memory-row.tsx | — | 2 | 1 |
| apps/web/components/agents/agent-policy-editor.tsx | Dialog | 5 | 3 |
| apps/web/components/agents/agent-reference-folders-editor.tsx | — | 6 | 1 |
| apps/web/components/agents/fleet-v4/agent-capability-overview.tsx | — | 2 | 16 |
| apps/web/components/agents/fleet-v4/agent-fleet-inspector.tsx | — | 9 | 17 |
| apps/web/components/agents/fleet-v4/agent-inspector.tsx | Sheet | 0 | 17 |
| apps/web/components/agents/fleet-v4/appearance-picker.tsx | — | 2 | 17 |
| apps/web/components/agents/fleet-v4/fleet-controls.tsx | — | 4 | 17 |
| apps/web/components/agents/fleet-v4/fleet-prototype-shell.tsx | AgentInspector | 4 | 17 |
| apps/web/components/agents/fleet-v4/gravitre-agent-card.tsx | — | 2 | 17 |
| apps/web/components/agents/fleet-v4/gravitre-agent-row.tsx | — | 1 | 17 |
| apps/web/components/agents/knowledge/agent-knowledge-add-sheet.tsx | Sheet | 2 | 1 |
| apps/web/components/agents/knowledge/agent-knowledge-card.tsx | DropdownMenu | 5 | 2 |
| apps/web/components/agents/knowledge/agent-knowledge-retrieval-tab.tsx | — | 2 | 1 |
| apps/web/components/agents/knowledge/agent-knowledge-shot-harness.tsx | — | 1 | 1 |
| apps/web/components/agents/knowledge/agent-knowledge-sources-tab.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle | 4 | 2 |
| apps/web/components/assignments/assignment-create-workspace.tsx | — | 15 | 1 |
| apps/web/components/assignments/assignment-detail-surfaces.tsx | Dialog | 12 | 1 |
| apps/web/components/billing/trial-expired-banner.tsx | — | 2 | 114 |
| apps/web/components/billing/upgrade-modal.tsx | Dialog | 3 | 114 |
| apps/web/components/connectors/available-connectors-strip.tsx | — | 4 | 16 |
| apps/web/components/connectors/connector-linkage.tsx | — | 3 | 1 |
| apps/web/components/connectors/connector-operating.tsx | ConnectorInspector, Sheet | 9 | 16 |
| apps/web/components/connectors/connector-recommendations.tsx | — | 2 | 16 |
| apps/web/components/connectors/knowledge-sync-button.tsx | — | 1 | 1 |
| apps/web/components/docs/docs-search.tsx | — | 2 | 1 |
| apps/web/components/docs/docs-shell.tsx | — | 3 | 1 |
| apps/web/components/docs/docs-sidebar.tsx | — | 1 | 1 |
| apps/web/components/docs/faq-experience.tsx | — | 3 | 1 |
| apps/web/components/docs/mdx-client.tsx | — | 2 | 2 |
| apps/web/components/enterprise/agent-roi-panel.tsx | — | 1 | 1 |
| apps/web/components/enterprise/apply-suggestion-result-sheet.tsx | Sheet | 5 | 1 |
| apps/web/components/enterprise/branding-tab.tsx | — | 11 | 1 |
| apps/web/components/enterprise/cs-dashboard-tab.tsx | ApplySuggestionResultSheet | 11 | 1 |
| apps/web/components/enterprise/knowledge-sync-tab.tsx | — | 3 | 1 |
| apps/web/components/enterprise/platform-org-view-banner.tsx | — | 2 | 1 |
| apps/web/components/enterprise/region-tab.tsx | Dialog | 4 | 1 |
| apps/web/components/enterprise/siem-tab.tsx | — | 7 | 1 |
| apps/web/components/federation/create-delegated-task-dialog.tsx | Dialog | 9 | 1 |
| apps/web/components/federation/create-handoff-dialog.tsx | Dialog | 9 | 1 |
| apps/web/components/federation/federation-delegated-task-list.tsx | — | 3 | 1 |
| apps/web/components/federation/federation-grant-list.tsx | — | 4 | 1 |
| apps/web/components/federation/handoff-timeline.tsx | — | 2 | 1 |
| apps/web/components/federation/invite-partner-dialog.tsx | Dialog | 5 | 1 |
| apps/web/components/federation/partner-card.tsx | — | 3 | 1 |
| apps/web/components/federation/propose-grant-dialog.tsx | Dialog | 9 | 1 |
| apps/web/components/gravitre/add-data-source-modal.tsx | Dialog | 16 | 16 |
| apps/web/components/gravitre/agent-capabilities-editor.tsx | — | 6 | 2 |
| apps/web/components/gravitre/agent-identity-editor.tsx | Dialog | 8 | 2 |
| apps/web/components/gravitre/agent-identity-governance-card.tsx | — | 5 | 2 |
| apps/web/components/gravitre/agent-identity-picker.tsx | — | 2 | 20 |
| apps/web/components/gravitre/agent-personality-section.tsx | — | 1 | 3 |
| apps/web/components/gravitre/agent-profile-editors.tsx | — | 4 | 2 |
| apps/web/components/gravitre/agent-ui/thinking-row.tsx | — | 1 | 175 |
| apps/web/components/gravitre/agent-ui/tool-execution-group.tsx | — | 1 | 175 |
| apps/web/components/gravitre/agent-voice-assignment.tsx | — | 12 | 4 |
| apps/web/components/gravitre/ai-context-indicator.tsx | — | 1 | 175 |
| apps/web/components/gravitre/ai-floating-workspace.tsx | ChatWindowControls | 0 | 175 |
| apps/web/components/gravitre/ai-insights-panel.tsx | Dialog | 12 | 175 |
| apps/web/components/gravitre/ai-mobile-sheet.tsx | ChatWindowControls, Drawer, GravitreAIMobileSheetSnapMode | 0 | 175 |
| apps/web/components/gravitre/ai-right-panel.tsx | — | 1 | 175 |
| apps/web/components/gravitre/ai-runtime-details.tsx | GravitreInspector, GravitreInspectorFields, GravitreInspectorNotice, GravitreInspectorSection | 1 | 175 |
| apps/web/components/gravitre/ai-workspace-shell.tsx | ChatWindowControls | 2 | 175 |
| apps/web/components/gravitre/app-shell.tsx | UpgradeModal | 3 | 114 |
| apps/web/components/gravitre/ask-prompt-chips.tsx | — | 1 | 17 |
| apps/web/components/gravitre/assignments/new-assignment-modal.tsx | Dialog | 13 | 16 |
| apps/web/components/gravitre/assistant/assistant-markdown.tsx | — | 1 | 175 |
| apps/web/components/gravitre/assistant/chat-execution-panel.tsx | — | 4 | 175 |
| apps/web/components/gravitre/assistant/chat-session-controls.tsx | DropdownMenu | 3 | 175 |
| apps/web/components/gravitre/assistant/chat-theme-picker.tsx | Popover | 2 | 175 |
| apps/web/components/gravitre/assistant/chat-transcript.tsx | — | 3 | 175 |
| apps/web/components/gravitre/assistant/clarification-message.tsx | — | 1 | 175 |
| apps/web/components/gravitre/assistant/conversation-sidebar.tsx | AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, DropdownMenu | 25 | 175 |
| apps/web/components/gravitre/assistant/explainability-panel.tsx | — | 1 | 175 |
| apps/web/components/gravitre/assistant/file-reference-chip.tsx | — | 1 | 175 |
| apps/web/components/gravitre/assistant/preview-code-pane.tsx | — | 2 | 175 |
| apps/web/components/gravitre/assistant/read-aloud-button.tsx | — | 1 | 175 |
| apps/web/components/gravitre/assistant/research-scope-prompt.tsx | — | 1 | 175 |
| apps/web/components/gravitre/assistant/shared-chat-composer-controls.tsx | — | 5 | 175 |
| apps/web/components/gravitre/assistant/task-side-panel.tsx | — | 1 | 175 |
| apps/web/components/gravitre/assistant/tool-chip.tsx | — | 1 | 175 |
| apps/web/components/gravitre/assistant/voice-mic-settings-popover.tsx | Popover | 4 | 175 |
| apps/web/components/gravitre/assistant/voice-mode-toggle.tsx | — | 3 | 175 |
| apps/web/components/gravitre/assistant/voice-presentation.tsx | — | 5 | 175 |
| apps/web/components/gravitre/assistant/voice-session-presence.tsx | — | 2 | 175 |
| apps/web/components/gravitre/built-in-models-brain.tsx | — | 7 | 3 |
| apps/web/components/gravitre/business-outcome/business-outcome-view.tsx | — | 1 | 175 |
| apps/web/components/gravitre/chat-window-controls.tsx | ChatWindowControlId | 1 | 175 |
| apps/web/components/gravitre/command-palette.tsx | CommandDialog | 0 | 114 |
| apps/web/components/gravitre/data-freshness.tsx | — | 1 | 32 |
| apps/web/components/gravitre/data-table.tsx | — | 1 | 16 |
| apps/web/components/gravitre/empty-state.tsx | — | 2 | 175 |
| apps/web/components/gravitre/filter-chip.tsx | — | 3 | 24 |
| apps/web/components/gravitre/global-command-bar.tsx | — | 3 | 114 |
| apps/web/components/gravitre/goal-workflow-wizard.tsx | Dialog | 16 | 114 |
| apps/web/components/gravitre/hub-tabs.tsx | — | 1 | 27 |
| apps/web/components/gravitre/inspector/gravitre-inspector.tsx | GravitreInspectorKind, Sheet | 0 | 175 |
| apps/web/components/gravitre/meson-page-panel.tsx | — | 2 | 175 |
| apps/web/components/gravitre/meson-toolbar-popup.tsx | — | 5 | 114 |
| apps/web/components/gravitre/meson-wizard.tsx | — | 15 | 17 |
| apps/web/components/gravitre/model-detail-insights.tsx | — | 5 | 1 |
| apps/web/components/gravitre/model-selector.tsx | — | 5 | 3 |
| apps/web/components/gravitre/notification-center.tsx | — | 5 | 175 |
| apps/web/components/gravitre/onboarding-checklist.tsx | — | 4 | 175 |
| apps/web/components/gravitre/open-gravitre-ai-button.tsx | — | 1 | 19 |
| apps/web/components/gravitre/operating/operating-primitives.tsx | — | 2 | 22 |
| apps/web/components/gravitre/pre-action-card.tsx | — | 4 | 175 |
| apps/web/components/gravitre/route-error.tsx | — | 1 | 175 |
| apps/web/components/gravitre/selection-inspector.tsx | Sheet | 0 | 3 |
| apps/web/components/gravitre/sidebar.tsx | — | 3 | 114 |
| apps/web/components/gravitre/source-query-panel.tsx | — | 3 | 1 |
| apps/web/components/gravitre/suggested-actions.tsx | Dialog | 9 | 175 |
| apps/web/components/gravitre/top-bar.tsx | DropdownMenu | 19 | 114 |
| apps/web/components/gravitre/window-manager/gravitre-docked-shell.tsx | ChatWindowControls, GravitreWindowFrame | 0 | 1 |
| apps/web/components/gravitre/window-manager/gravitre-window-manager-shell.tsx | ChatWindowControls, GravitreWindowFrame | 2 | 1 |
| apps/web/components/gravitre/work-decision-dialog.tsx | Dialog | 2 | 7 |
| apps/web/components/gravitre/work-section-error-card.tsx | — | 2 | 175 |
| apps/web/components/gravitre/workflow-card.tsx | DropdownMenu | 6 | 16 |
| apps/web/components/home/home-dashboard.tsx | KpiPickerDialog | 12 | 16 |
| apps/web/components/home/kpi-picker-dialog.tsx | Dialog | 3 | 16 |
| apps/web/components/home/operating-flow.tsx | — | 3 | 16 |
| apps/web/components/intelligence/ask-gravitre-composer.tsx | — | 5 | 24 |
| apps/web/components/intelligence/ask-gravitre-entry.tsx | — | 2 | 24 |
| apps/web/components/intelligence/ask-gravitre-summon-button.tsx | — | 1 | 31 |
| apps/web/components/intelligence/business-model-card.tsx | BusinessModelInspector | 1 | 1 |
| apps/web/components/intelligence/graph/intelligence-graph-list.tsx | — | 1 | 24 |
| apps/web/components/intelligence/graph/intelligence-graph-stage.tsx | — | 5 | 24 |
| apps/web/components/intelligence/graph/intelligence-graph-toolbar.tsx | DropdownMenu | 10 | 24 |
| apps/web/components/intelligence/heuristic-suggestion-cards.tsx | — | 1 | 16 |
| apps/web/components/intelligence/intelligence-change-stream.tsx | — | 1 | 16 |
| apps/web/components/intelligence/intelligence-health-grid.tsx | — | 1 | 16 |
| apps/web/components/intelligence/intelligence-matrix-lens.tsx | — | 2 | 16 |
| apps/web/components/intelligence/journey-rails.tsx | — | 4 | 16 |
| apps/web/components/intelligence/learning-insight-card.tsx | LearningInsightInspector | 1 | 1 |
| apps/web/components/intelligence/map/intelligence-inspector-drawer.tsx | Sheet | 5 | 16 |
| apps/web/components/intelligence/map/intelligence-support-sections.tsx | — | 1 | 16 |
| apps/web/components/intelligence/outcome-attribution-flow.tsx | StepInspector | 2 | 2 |
| apps/web/components/intelligence/pages/learning-stage.tsx | — | 1 | 1 |
| apps/web/components/intelligence/pages/model-studio-stage.tsx | SelectionInspector | 13 | 1 |
| apps/web/components/intelligence/pages/models-stage.tsx | — | 1 | 1 |
| apps/web/components/intelligence/pages/overview-living-map.tsx | IntelligenceInspectorDrawer | 7 | 16 |
| apps/web/components/intelligence/pages/predictions-stage.tsx | — | 1 | 1 |
| apps/web/components/intelligence/pages/reports-stage.tsx | — | 4 | 1 |
| apps/web/components/intelligence/relationships/add-knowledge-node-sheet.tsx | Sheet | 5 | 4 |
| apps/web/components/intelligence/relationships/duplicate-match-panel.tsx | — | 2 | 4 |
| apps/web/components/intelligence/relationships/relationship-inspector.tsx | — | 13 | 4 |
| apps/web/components/intelligence/relationships/relationship-legend.tsx | — | 1 | 4 |
| apps/web/components/intelligence/relationships/relationship-table-view.tsx | — | 3 | 4 |
| apps/web/components/intelligence/relationships/relationship-toolbar.tsx | — | 10 | 4 |
| apps/web/components/intelligence/relationships/relationships-workspace.tsx | AddKnowledgeNodeSheet, RelationshipInspector, Sheet | 1 | 4 |
| apps/web/components/intelligence/training-readiness-strip.tsx | — | 2 | 16 |
| apps/web/components/intelligence/why-gravitre-panel.tsx | — | 1 | 16 |
| apps/web/components/marketing/creative/scenes/agent-orchestration/orchestration-field.tsx | — | 6 | 5 |
| apps/web/components/marketing/creative/scenes/connector-fabric/connector-fabric-field.tsx | — | 3 | 5 |
| apps/web/components/marketing/creative/scenes/gibe-learning/gibe-learning-field.tsx | — | 2 | 5 |
| apps/web/components/marketing/creative/scenes/governed-execution/governed-execution-field.tsx | — | 2 | 5 |
| apps/web/components/marketing/creative/scenes/knowledge-fabric/entity-convergence-workbench-refined.tsx | — | 6 | 6 |
| apps/web/components/marketing/creative/scenes/knowledge-fabric/entity-convergence-workbench.tsx | — | 6 | 6 |
| apps/web/components/marketing/creative/scenes/voice-intent/voice-intent-field.tsx | — | 2 | 5 |
| apps/web/components/marketing/features/extension-page.tsx | — | 2 | 1 |
| apps/web/components/marketing/features/features-page.tsx | — | 2 | 1 |
| apps/web/components/marketing/features/marketplace-page.tsx | — | 1 | 1 |
| apps/web/components/marketing/features/technology-page.tsx | — | 2 | 1 |
| apps/web/components/marketing/marketing-consent-banner.tsx | — | 8 | 28 |
| apps/web/components/marketing/nodus/agentic-intelligence/skeletons.tsx | — | 2 | 1 |
| apps/web/components/marketing/nodus/cta.tsx | — | 1 | 22 |
| apps/web/components/marketing/nodus/faqs.tsx | — | 3 | 1 |
| apps/web/components/marketing/nodus/footer.tsx | — | 3 | 28 |
| apps/web/components/marketing/nodus/hero.tsx | — | 2 | 1 |
| apps/web/components/marketing/nodus/home-pricing-cta.tsx | — | 1 | 1 |
| apps/web/components/marketing/nodus/how-it-works/index.tsx | — | 1 | 1 |
| apps/web/components/marketing/nodus/navbar-desktop.tsx | — | 1 | 28 |
| apps/web/components/marketing/nodus/navbar-floating.tsx | — | 1 | 28 |
| apps/web/components/marketing/nodus/navbar-mobile.tsx | — | 4 | 28 |
| apps/web/components/marketing/nodus/pricing-table.tsx | — | 2 | 1 |
| apps/web/components/marketing/nodus/pricing.tsx | — | 2 | 1 |
| apps/web/components/marketing/pricing/pricing-faq-accordion.tsx | — | 1 | 1 |
| apps/web/components/marketing/system/gsap-site-story-sticky.tsx | — | 1 | 22 |
| apps/web/components/marketplace/asset-outcome-editor.tsx | — | 4 | 1 |
| apps/web/components/marketplace/asset-pricing-editor.tsx | — | 3 | 2 |
| apps/web/components/marketplace/asset-purchase-button.tsx | — | 1 | 18 |
| apps/web/components/marketplace/asset-reviews-section.tsx | MarketplaceDecisionDialog | 6 | 2 |
| apps/web/components/marketplace/asset-save-button.tsx | — | 2 | 19 |
| apps/web/components/marketplace/asset-version-history.tsx | — | 4 | 1 |
| apps/web/components/marketplace/department-pipeline-panel.tsx | — | 1 | 19 |
| apps/web/components/marketplace/install-experience.tsx | Sheet | 10 | 18 |
| apps/web/components/marketplace/marketplace-asset-commerce.tsx | — | 1 | 19 |
| apps/web/components/marketplace/marketplace-featured-outcome.tsx | — | 1 | 16 |
| apps/web/components/plays/play-results.tsx | — | 1 | 1 |
| apps/web/components/plays/play-run-control.tsx | — | 1 | 1 |
| apps/web/components/plays/play-setup.tsx | — | 3 | 1 |
| apps/web/components/runs/approval-batch-panel.tsx | — | 3 | 1 |
| apps/web/components/runs/execution-timeline.tsx | — | 7 | 1 |
| apps/web/components/schedules/schedule-editor-dialog.tsx | Dialog | 11 | 4 |
| apps/web/components/settings/api-keys-settings.tsx | — | 7 | 1 |
| apps/web/components/settings/memory-entity-embeddings-settings.tsx | — | 3 | 1 |
| apps/web/components/settings/notification-settings.tsx | — | 6 | 1 |
| apps/web/components/settings/organization-settings.tsx | — | 2 | 1 |
| apps/web/components/settings/security-settings.tsx | Dialog | 15 | 1 |
| apps/web/components/settings/settings-shell.tsx | Sheet | 2 | 9 |
| apps/web/components/settings/team-settings.tsx | Dialog | 13 | 1 |
| apps/web/components/settings/webhooks-settings.tsx | Dialog | 7 | 1 |
| apps/web/components/sources/source-inspector.tsx | — | 5 | 16 |
| apps/web/components/ui/alert-dialog.tsx | AlertDialogOverlay, AlertDialogPortal, AlertDialogPrimitive.Action, AlertDialogPrimitive.Cancel, AlertDialogPrimitive.Content, AlertDialogPrimitive.Description, AlertDialogPrimitive.Overlay, AlertDialogPrimitive.Portal, AlertDialogPrimitive.Root, AlertDialogPrimitive.Title, AlertDialogPrimitive.Trigger | 0 | 175 |
| apps/web/components/ui/command.tsx | Dialog | 0 | 114 |
| apps/web/components/ui/input.tsx | — | 1 | 175 |
| apps/web/components/ui/textarea.tsx | — | 1 | 116 |
| apps/web/components/workflows/builder-chrome.tsx | — | 6 | 3 |
| apps/web/components/workflows/failure-alerts-panel.tsx | — | 6 | 16 |
| apps/web/components/workflows/failure-prediction-alerts.tsx | — | 2 | 17 |
| apps/web/components/workflows/integration-suggestion-evidence-banner.tsx | — | 1 | 2 |
| apps/web/components/workflows/intelligence-drawer.tsx | Sheet | 5 | 3 |
| apps/web/components/workflows/meson-copilot-panel.tsx | — | 11 | 2 |
| apps/web/components/workflows/workflow-pre-run-panel.tsx | — | 3 | 1 |
| apps/web/lib/chat-window-state.ts | ChatWindowControlId, ChatWindowControls | 0 | 175 |
