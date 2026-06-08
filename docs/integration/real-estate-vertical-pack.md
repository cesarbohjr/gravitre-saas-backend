# Real estate vertical pack (STA-115)

Industry pack for brokerages: HubSpot buyer lookup, MLS note templates, listing coordinator and buyer agent handoff workflow.

## Prerequisites

- [HubSpot connector (STA-13)](./hubspot-oauth.md) optional — workflow skips CRM search if not connected
- [Agent tool permissions (STA-11)](./agent-tool-permissions.md)

## Install

```http
POST /api/verticals/real-estate/install
Authorization: Bearer <admin-token>
```

Installs:

| Asset | Description |
|-------|-------------|
| Listing Coordinator Agent | MLS note prep and listing launch |
| Buyer Agent Handoff Agent | Packages buyer briefing for handoff |
| Listing workflow | HubSpot buyer search → MLS note → agents → handoff brief |

```http
GET /api/verticals/real-estate
```

## Tools

| Action | Description |
|--------|-------------|
| `real_estate.mls.note` | MLS-ready listing note sections |
| `real_estate.handoff.brief` | Buyer agent handoff checklist |

## Workflow parameters

| Parameter | Default |
|-----------|---------|
| `property_address` | `742 Evergreen Terrace` |
| `list_price` | `450000` |
| `buyer_name` | `Jamie Buyer` |
| `buyer_email` | `buyer@example.com` |

## Related

- STA-114 Legal vertical pack
- STA-113 Healthcare vertical pack
