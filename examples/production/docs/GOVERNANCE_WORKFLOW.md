# Governance workflow: dev → stage → prod

Maps to the FastAPI routes under `/governance/*` and the in-memory `PromotionRegistry` (swap for your durable store in production).

## 1. Environments

Default pin environments: **dev**, **stage**, **prod** (see `GET /governance/environments`).

| Environment | Purpose |
|-------------|---------|
| dev | Developer sandboxes; may auto-sync from “active” metadata version |
| stage | Pre-prod validation; shadow traffic and parity checks |
| prod | Customer-impacting decisions |

## 2. Happy path

1. **Author** creates or updates a rule via `POST /rules` (namespace = tenant).
2. **Sync dev** — `POST /governance/sync-dev` sets the dev pin to the **currently time-active** version for the handle (`sync_dev_from_active`).
3. **Promote** — `POST /governance/promote` moves pins **only between adjacent** environments (dev→stage, stage→prod). Validate stored version with `validate_version_namespace` semantics.
4. **Deploy** — your Spark / streaming job loads the DRL (or RulePack) for the **target environment** pin from your artifact pipeline.

## 3. Platform administrator

Users with **`platform_admin`** may operate across namespaces; the API resolves the **canonical namespace from the active rule** for `sync-dev` so pins land on the correct tenant partition. Tenant-scoped operators still use `X-Tenant-Id` aligned with body `namespace`.

## 4. Rollback

### 4.1 Fast rollback (pin only)

1. Identify last known-good **version** int for `{namespace, rule_handle}`.
2. Use your registry’s **force pin** (if you expose it) or re-run `promote` from a branch that restores metadata — the stock API promotes from existing pins; for emergency override, use a controlled admin endpoint or SQL update on your metadata store **with audit**.

### 4.2 Code + rules rollback

1. Roll container / wheel to **N-1**.
2. Restore pins from backup JSON (export pins periodically via `GET /governance/pins`).

## 5. Deprecation

1. `POST /governance/deprecations/propose` — reason documented.
2. `POST /governance/deprecations/approve` — second pair of eyes (separate principal in prod).
3. `POST /governance/deprecations/enforce` — deactivates versions per policy; re-run idempotent.

After enforce, **sync-dev** picks the next active version automatically on the next promotion cycle.

## 6. Audit

Every mutating governance call should emit audit rows (`governance_sync_dev`, `governance_promote`, …). Ship logs to SIEM; correlate with **Git commit** of DRL and **SBOM** image digest.

## 7. Checklist before prod promotion

- [ ] Unit + property tests green for the DRL change set  
- [ ] Shadow parity summary within threshold (see [canary.yaml](../k8s/canary.yaml) pattern)  
- [ ] `max_rulepack_bytes` not exceeded in CI and prod env  
- [ ] Threat model updates if new external dependency or data flow  
