export type EnterpriseTabId = "region" | "branding" | "analytics" | "siem" | "cost"

export interface DnsInstructions {
  domain?: string
  cnameTarget?: string
  cnameRecord?: { type: string; host: string; value: string }
  txtRecord?: { type: string; host: string; value: string }
}

export interface DomainVerifyResult {
  verified?: boolean
  method?: string | null
  checks?: {
    cname?: { expected?: string; found?: string[] }
    txt?: { expected?: string; found?: string[] }
  }
}
