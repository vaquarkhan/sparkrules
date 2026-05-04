# Security hardening beyond metrics and rule-pack size

`SPARKRULES_ENGINE_METRICS` and `SPARKRULES_MAX_RULEPACK_BYTES` are necessary but **not sufficient**. Use this checklist with [THREAT_MODEL.md](THREAT_MODEL.md).

## Authentication and authorization

| Control | Configuration |
|---------|----------------|
| OIDC | `SPARKRULES_AUTH_MODE=oidc`, set issuer + audience env vars (see API security module) |
| mTLS | `SPARKRULES_AUTH_MODE=mtls`; terminate TLS at ingress with client cert verification |
| IAM / cloud identity | `SPARKRULES_AUTH_MODE=iam`; map `x-iam-principal` from your gateway |
| Default superuser | **Never** set `SPARKRULES_DEV_ALLOW_DEFAULT_SUPERUSER=true` in prod |

## Transport

- TLS 1.2+ everywhere; **HSTS** on public ingress.
- **mTLS** between services where supported (API ↔ metadata DB via stunnel or mesh).

## Secrets

- No DRL or tokens in **ConfigMaps** unencrypted; use **External Secrets Operator** + cloud KMS.
- Rotate Kafka and DB passwords on schedule.

## Rate limiting and abuse

- Per-IP and per-**tenant** rate limits on `/rules`, `/simulate`, `/governance/*`.
- **Max request body** at reverse proxy (e.g. 4 MiB unless importing large packs via separate flow).

## Observability without leakage

- `/metrics` text must not include tenant labels with high cardinality; prefer aggregate counters.
- Redact **PII** in structured logs; hash `fact_id` in traces if required by policy.

## Spark isolation

- **Queue** per tenant on YARN / K8s scheduler.
- **ACLs** on checkpoint and output paths (S3 bucket policies / ABAC).
- Disable **Spark UI** wide open; authenticate or VPN-only.

## Dependency and runtime

- **Read-only** root filesystem for API pods where possible.
- **seccomp** / **AppArmor** profiles on Kubernetes.
- **FIPS**-validated OpenSSL if mandated (use base images certified for your jurisdiction).

## Incident response

- Document **who** can use `platform_admin` and **time-bound** elevation.
- Run tabletop exercises for “bad DRL promoted to prod” — rollback steps in [GOVERNANCE_WORKFLOW.md](GOVERNANCE_WORKFLOW.md).

## Compliance mapping (informative)

| Framework | Typical mappings |
|-----------|-------------------|
| SOC 2 CC | Access control, logging, change management |
| ISO 27001 | A.8, A.12, A.14 |
| PCI DSS | If scoring touches cardholder data — segment networks and scope reduction |
