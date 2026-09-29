# Gravitre Plays / Outcomes — dashboard integration decision

Date: 2026-09-29

## Decision

Do not create a Plays dashboard product or a parallel analytics shell.

The existing authenticated Dashboard remains the customer surface. Play
readiness and verified outcomes appear inside its existing operating/Measure
composition.

## Existing dashboard substrate

The current Dashboard already owns:

- operating flow;
- configured KPI Measure strip;
- outcome flow visualization;
- revenue-risk signals;
- approvals;
- agent status;
- learning/intelligence status;
- configurable widgets and presets.

The first Play integration therefore extends:

- `useHomeDashboardData`;
- `HomeDashboard`;
- existing Dashboard Measure.

## First integration

The Dashboard now consumes `GET /api/plays` and renders an **Outcome plays**
readiness strip inside Measure.

It displays only canonical readiness states:

- OBSERVE
- RECOMMEND
- ACT WITH APPROVAL
- ACT WITHIN POLICY
- CONNECTION REQUIRED / PARTIAL / MISSING when appropriate

No Play is shown as ACT WITHIN POLICY merely because policy rows are absent.

## What is intentionally not displayed yet

The Dashboard does not display:

- recovered revenue;
- retained revenue;
- churn avoided;
- pipeline influenced;
- revenue influenced;

unless verified Play business-result events support those claims.

The first three observe endpoints explicitly return null business impact for
unverified opportunities.

## Future template architecture

Executive Overview, Customer Rescue, Revenue Recovery, Marketing Performance
and Custom remain **views/presets over the existing Dashboard**, not separate
dashboard applications.

A future Play-specific view may filter or emphasize:

- Play readiness;
- current signals/recommendations;
- pending approvals;
- canonical workflow runs;
- verified Play business-result events;
- evidence links.

The underlying stores and Dashboard remain shared.

## Result

DASHBOARD_DUPLICATION = AVOIDED

PLAY_READINESS_ON_EXISTING_DASHBOARD = IMPLEMENTED

PLAY_BUSINESS_IMPACT_WIDGETS = BLOCKED_UNTIL_VERIFIED_OUTCOME_DATA
