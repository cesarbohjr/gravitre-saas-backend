# PR581 progressive connector migration

The shared connector profile is descriptive setup guidance, never an execution grant. Published agents install without connected apps; live tools retain existing request-time IAM, connector, quota, approval and cancellation checks. Non-agent installation prerequisites remain unchanged.

## Catalog census

| Agent | Recommendations, in priority order | Offline-only rationale |
|---|---|---|
| `marketing-analyst` | Google Ads, Google Analytics, HubSpot | Strategy, drafts and supplied evidence are available before connection. |
| `product-icp-strategist` | HubSpot | Strategy, drafts and supplied evidence are available before connection. |
| `content-writer` | HubSpot | Strategy, drafts and supplied evidence are available before connection. |
| `marketing-designer` | Canva | Strategy, drafts and supplied evidence are available before connection. |
| `marketing-ops-coordinator` | HubSpot, Google Analytics | Strategy, drafts and supplied evidence are available before connection. |
| `seo-analyst` | Google Analytics, Google Search Console, Google Ads | Strategy, drafts and supplied evidence are available before connection. |
| `competitor-research-agent` | HubSpot | Strategy, drafts and supplied evidence are available before connection. |
| `revenue-operations-agent` | HubSpot, Salesforce | Strategy, drafts and supplied evidence are available before connection. |
| `sales-pipeline-agent` | HubSpot, Salesforce | Strategy, drafts and supplied evidence are available before connection. |
| `customer-success-agent` | HubSpot | Strategy, drafts and supplied evidence are available before connection. |
| `ticket-triage` | Zendesk | Strategy, drafts and supplied evidence are available before connection. |
| `cfo-agent` | QuickBooks | Strategy, drafts and supplied evidence are available before connection. |
| `sdr-coach` | HubSpot | Strategy, drafts and supplied evidence are available before connection. |
| `lead-enrichment-coordinator` | Apollo, Clay, HubSpot | Strategy, drafts and supplied evidence are available before connection. |
| `ppc-campaign-strategist` | Google Ads, Google Analytics | Strategy, drafts and supplied evidence are available before connection. |
| `programmatic-display-buyer` | Google Ads, Google Analytics, Demand-side buying platform (not supported) | Strategy, drafts and supplied evidence are available before connection. |
| `paid-social-strategist` | HubSpot, Meta Ads (not supported), TikTok Ads (not supported), LinkedIn Ads (not supported) | Strategy, drafts and supplied evidence are available before connection. |
| `studio-producer` | Jira, Slack | Strategy, drafts and supplied evidence are available before connection. |
| `project-shepherd` | Jira, Slack | Strategy, drafts and supplied evidence are available before connection. |
| `studio-operations` | Notion, Slack | Strategy, drafts and supplied evidence are available before connection. |
| `experiment-tracker` | Google Sheets, Notion | Strategy, drafts and supplied evidence are available before connection. |
| `senior-project-manager` | Jira, Confluence | Strategy, drafts and supplied evidence are available before connection. |
| `jira-workflow-steward` | Jira, GitHub | Strategy, drafts and supplied evidence are available before connection. |
| `meeting-notes-specialist` | Google Drive, Slack | Strategy, drafts and supplied evidence are available before connection. |
| `frontend-developer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `backend-architect` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `mobile-app-builder` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `ai-engineer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `devops-automator` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `senior-developer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `codebase-onboarding-engineer` | GitHub, Confluence | Strategy, drafts and supplied evidence are available before connection. |
| `database-optimizer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `sre` | GitHub, PagerDuty, Slack | Strategy, drafts and supplied evidence are available before connection. |
| `data-engineer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `cms-developer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `api-platform-engineer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `voice-ai-integration-engineer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `it-service-manager` | Servicenow (not supported), Zendesk, Slack | Strategy, drafts and supplied evidence are available before connection. |
| `payments-billing-engineer` | GitHub, Stripe | Strategy, drafts and supplied evidence are available before connection. |
| `identity-access-engineer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `privacy-engineer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `universal-document-compiler` | GitHub, Google Drive | Strategy, drafts and supplied evidence are available before connection. |
| `technical-writer` | GitHub, Confluence | Strategy, drafts and supplied evidence are available before connection. |
| `servicenow-developer-mentor` | Servicenow (not supported), GitHub | Strategy, drafts and supplied evidence are available before connection. |
| `solidity-smart-contract-engineer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `test-automation-engineer` | GitHub, Jira | Strategy, drafts and supplied evidence are available before connection. |
| `content-strategist-agent` | HubSpot, Google Analytics | Strategy, drafts and supplied evidence are available before connection. |
| `pipeline-forecast-agent` | Salesforce | Strategy, drafts and supplied evidence are available before connection. |
| `renewal-risk-agent` | HubSpot | Strategy, drafts and supplied evidence are available before connection. |
| `finance-variance-agent` | None | This agent can work from conversation and supplied evidence; no external integration is needed for its advisory role. |
| `it-incident-triage-agent` | PagerDuty, Slack, GitHub | Strategy, drafts and supplied evidence are available before connection. |
| `talent-pipeline-agent` | None | This agent can work from conversation and supplied evidence; no external integration is needed for its advisory role. |
| `msp3-msp-service-coordinator` | Zendesk, Freshservice, Servicenow (not supported), Halo Psa (not supported), Autotask (not supported), ConnectWise, Syncro (not supported) | Strategy, drafts and supplied evidence are available before connection. |
| `msp3-msp-resolution-engineer` | Microsoft Intune (not supported), Jumpcloud (not supported), Jamf Pro (not supported), Huntress (not supported), Sentinelone (not supported), Crowdstrike (not supported), Freshservice | Strategy, drafts and supplied evidence are available before connection. |
| `msp3-msp-service-analyst` | Zendesk, Freshservice, Servicenow (not supported), Halo Psa (not supported), Autotask (not supported), ConnectWise, Syncro (not supported) | Strategy, drafts and supplied evidence are available before connection. |

## Shared surfaces

- Marketplace browse readiness, details, previews and installation.
- Installed-agent detail and fleet inspection; connector settings for the selected agent.
- Shared full and compact prompts used by text and voice.
- Recommendations distinguish first, next and optional; connected, available, attention and unsupported states.
- Fresh tenant/environment-scoped reads; database errors fail closed; unsupported integrations have no connection action.

## Evidence and limits

- Backend Marketplace/shared-prompt/recommendation suite: 738 passed before the final injection/scope tests were added.
- Full web Vitest suite: 1,960 passed across 312 files. UI recommendation and listing readiness: 11 passed (overlap); TypeScript passed; touched-file ESLint passed with existing warnings in connector settings.
- Legacy listing tests now exercise required-app blocking on workflows; added agent assertions preserve binding review. This implements the approved policy change and does not relax execution authorization.
- Final recommendation suite including prompt injection and private-asset scope: 31 passed (overlap).
- Prior unfinished workspace changes were recovered and reviewed; this checkpoint adds scope checks, injection filtering, URL encoding, failure tests, catalog coverage and UI copy correction.
- Final full CI and combined PR587 compatibility remain required. Live/provider/production acceptance remains NOT RUN until the coordinated release.
- Operations and software Engineering/IT implementations are recorded in their separate implementation records. Native worker activation, final full CI and combined compatibility remain open; offline engineering results are not production certification.
