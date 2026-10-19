# Billing acceptance migration reconciliation

Production project: `smyeexlrqdpymwjmgzqu`. User authorized reconciliation on 2026-10-19.

All 275 production versions now match the 275 repository versions. Six files were renamed to the already-applied production timestamps. Each SQL file matched the production-recorded statements byte for byte after trimming surrounding whitespace. No SQL, production data, or history records were changed.

| Migration | Recorded version | SQL SHA-256 |
| --- | --- | --- |
| stripe_meter_outbox | 20261016185052 | `e4cb3459909adf3adc0c1008f7068a17f0dbfa9560fbb57e247a73aeba138a15` |
| mcp_server_rate_limit | 20261017002821 | `1902cedc588d79155363a9abdb2a6208b73d413ab8afe62176cddee9343b5a32` |
| msp_delegations_restricted | 20261018032455 | `93d65beeb8e6c012fbb6fb7c9d84321a182cdfe25da87ffd30153ba94f315477` |
| msp_delegation_atomic_audit | 20261018032503 | `82801973ffcff88b3e0c463bd972d62b6948bb766f85328e8976975df2a5103a` |
| customer_segments_and_founder_offers | 20261019050504 | `456ff8e08901414fc87376c57f8336ad2d3e09c5e479ccf5ec8878ef5ce6948e` |
| founder_billing_safety | 20261019050855 | `912500bcb3bdbd740d01466391f5fbb312b91478b96be0a362261688b41d684d` |

Test and CI references were updated for the six canonical filenames. Historical release documents retain their original references as historical evidence.

Stripe sandbox, authenticated roles, and browser billing acceptance are separate from this filename reconciliation and require their own evidence.
