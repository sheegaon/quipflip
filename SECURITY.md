# Security Policy

Do not open a public issue containing a credential, session token, private player
data, or an exploitable pre-finalization information disclosure (for example, a
response that reveals authorship or which phrase is the original before a phraseset
finalizes).

Privately report the affected version/commit, reproduction steps, impact, and any
known exposure window to the repository owner. Do not include live secrets; revoke
or rotate them at the provider first.

Crowdcraft Labs runs a real flipcoin economy, so treat money-movement bugs
(double refunds, double payouts, balance manipulation) and lifecycle-integrity bugs
(orphaned or double-claimed rounds) as security-sensitive. See the
[security and secrets policy](docs/development/security-and-secrets.md) for
repository rules, transport hardening, and incident response.
