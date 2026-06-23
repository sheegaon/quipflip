# Deployment Inventory

> **Document type:** Operator record
> **Status:** Draft
> **Audience:** Maintainers and operators
> **Last reviewed:** 2026-06-22

This file records the deployment choices that F1 must not leave ambiguous. The
workstream plan treats these as fixed defaults unless an operator explicitly
changes them.

## Selected defaults

| Decision | Selected value |
| --- | --- |
| Heroku production data | Not retained. Cutover starts from a fresh production SQLite database. No DNS-rollback reconciliation path is planned for discarded historical data. |
| Production checkout path | `/Users/tfish/quipflip` |
| Operator account | `tfish` |
| Target Mac availability | Always-on AC power, wired network, and auto-login for the operator account. Remote recovery is via SSH or Screen Sharing when available, otherwise physical access. |
| Backup retention | Keep the current rollback candidate plus the last 3 successful backups. |
| Free-space threshold | At least 5 GiB free and at least 2x the current DB plus WAL size before release mutation. |
| Off-host backup location | An encrypted APFS volume or equivalent encrypted removable drive controlled by the operator. |
| Restore owner | `tfish` |
| Staging DNS | Four dedicated `staging.` aliases: `staging.quipflip.crowdcraftlabs.com`, `staging.mememint.crowdcraftlabs.com`, `staging.initialreaction.crowdcraftlabs.com`, and `staging.thinklink.crowdcraftlabs.com`. Each is routed through the named tunnel and mapped 1:1 to its game. |
| Soak duration | 72 hours |
| Rollback window | 72 hours |
| Rollback decision owner | `tfish` |
| Rollback triggers | Sustained readiness failure, integrity mismatch, or HTTP 5xx above 1% over 15 minutes. |
| AI provider policy | OpenAI is the primary provider and Gemini is the fallback for AIService-driven fill/vote flows. ThinkLink semantic matching remains OpenAI-backed; if OpenAI is unavailable, that feature is disabled and the rest of the game stays up. |
| Legacy browser clients | Not supported through cutover. Only the updated same-origin clients are required. |
| `cloudflared` owner | Repository LaunchAgent after cutover. Cloudflare dashboard setup only provisions the tunnel and DNS records. |

## Notes

- There are no current blocking `TBD` entries.
- If a future deployment choice changes, update this file first and then align
  the workstream and runbooks with the new value.
