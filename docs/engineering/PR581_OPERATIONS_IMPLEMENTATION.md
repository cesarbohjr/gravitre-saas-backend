# PR581 Project Management under Operations

All seven roles in the pinned audited Project Management division are included. No current seeded Marketplace agent owns project portfolio planning, delivery scope, experiments, meeting records or Jira workflow stewardship; these are distinct specialists rather than relabeled incident triage. Native shared intelligence and the existing DEFAULT enterprise persona are retained, supplemented by role-specific, provenance-checked guidance.

| Source | Gravitre destination | Decision | Recommendations |
|---|---|---|---|
| `project-management/project-management-studio-producer.md` (`d942feab0f50ea7b8e98cb73bdaf05226d2a6c53c6359c7380149f7545bb199d`) | `studio-producer` | New Operations specialist; distinct responsibility | jira, slack |
| `project-management/project-management-project-shepherd.md` (`0feb647366d78b61c1633b12e370ffb1dea52facb9d750ef6c952de1e996031c`) | `project-shepherd` | New Operations specialist; distinct responsibility | jira, slack |
| `project-management/project-management-studio-operations.md` (`8a2e5098d94688d191a128b6b2fdbbf3724bfcd2f4944766de6e25a0709f1517`) | `studio-operations` | New Operations specialist; distinct responsibility | notion, slack |
| `project-management/project-management-experiment-tracker.md` (`8f1410bfa054c8ac2eee3084b9bfdb3adb1e8a2f3e015c2876d0ecf07136c22f`) | `experiment-tracker` | New Operations specialist; distinct responsibility | google_sheets, notion |
| `project-management/project-manager-senior.md` (`70fb27cab174c97375293311211d5563c5ac257fba274450d1ca9c05b540ef2d`) | `senior-project-manager` | New Operations specialist; distinct responsibility | jira, confluence |
| `project-management/project-management-jira-workflow-steward.md` (`1e63812bd80317f4f69403701b6e1ff28d2fcf61862288f93fa4e4676bf46e17`) | `jira-workflow-steward` | New Operations specialist; distinct responsibility | jira, github |
| `project-management/project-management-meeting-notes-specialist.md` (`53a6efaa379b70cbc3276b44544ecf569789fffe892ba82eb68e8672407de91f`) | `meeting-notes-specialist` | New Operations specialist; distinct responsibility | google_drive, slack |

Each agent has a canonical advisory review workflow that binds to its installed tenant agent identity. Workflow outputs are draft evidence/decision/action registers, not external writes. Each agent installs without connectors, has zero default systems/tool grants and uses the same recommendation statuses and text/voice prompts. Recommendations do not imply support for every action exposed by an upstream project-management application.

Exact source revision: `b37b5bb33b78f2c1d6567d98e25ca818e3259219`, MIT. Per-agent immutable references use approval `PR581:user-approved-project-management-under-operations`. Seed updates publish a new immutable version; pending publication is denied even with force. Existing installations change only through explicit upgrade/rollback. No change to Operations pack membership, pricing or automatic installation.

Validation covers source census/hash equality, offline install/upgrade/rollback with stable identity, immutable baselines, text/voice prompt equality, zero grants, workflow bindings and unpublished-snapshot refusal. Full final-head CI and combined PR587 compatibility are still required. No seed, live install, merge, deployment or production certification has run.
