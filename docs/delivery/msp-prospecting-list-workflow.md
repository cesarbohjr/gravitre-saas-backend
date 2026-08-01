# MSP Prospecting & List Builder

Replaces the legacy **MSP NVD CVE Lookup** demo canvas workflow on the MSP Intelligence Pack.

## Goal

Prospect Managed Service Providers with **agents**, **connector tools**, and **assignment-style agent tasks**:

1. ICP / scouting brief (agent assignment + notify started)
2. Apollo company search (task)
3. Apollo people search (task)
4. Qualify + plan list membership (agent assignment)
5. Create Apollo list `MSP Prospects` (task)
6. Populate Apollo membership (agent assignment)
7. Create HubSpot list `MSPs` (task)
8. HubSpot sync + complete assignment notify (agent)

NVD / CISA KEV remain **knowledge assignments** for the MSP Vulnerability Analyst (not the primary canvas).

## Definition

`backend/app/marketplace/workflows/msp_prospecting_list_workflow.py`

## Install / upgrade

- Pack install upserts the same marketplace entity seed (`msp-nvd-workflow`) so existing org rows upgrade in place.
- Legacy title `MSP NVD CVE Lookup` is also matched by name and rewritten.
- Re-install **MSP Intelligence Pack** from Marketplace, or run pack install again for the org.

## Required connectors

- **Apollo** (customer-owned)
- **HubSpot** (customer-owned)
- **Clay** optional for enrichment path inside the final agent assignment
- NVD / CISA KEV still staged as Gravitree-managed knowledge sources
