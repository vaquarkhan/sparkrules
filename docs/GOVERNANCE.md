# Governance (Phase 4)

## Namespaces

Each rule has a `namespace` string (default `default`) for project or org scoping. It is stored on the rule, returned on `/rules/assets`, and included in **rule pack** import/export. Filter assets with the `namespace` query parameter.

## Environments and pins

The API uses three fixed **environments**: `dev` → `stage` → `prod`. The **in-memory** `PromotionRegistry` (per API process) records which **version** of a rule is “pinned” in each environment for a `(namespace, rule_handle)`.

- **Sync dev** (`POST /governance/sync-dev`) sets the `dev` pin to the current **time-resolved active** version for the handle, and checks that the request `namespace` matches the rule’s `namespace`.
- **Promote** (`POST /governance/promote`) only allows **adjacent** moves: `dev`→`stage` and `stage`→`prod`, copying the version from the source pin. The version must still exist in the store and match the namespace.

Runtime engines do **not** read these pins automatically; connect them in your deployment pipeline (e.g. only load `prod` pins in production).

## Deprecations

The **in-memory** `DeprecationRegistry` (per API process) supports a workflow to retire rules:

- **Propose**  -  record intent to deprecate a rule handle in a **namespace** (`POST /governance/deprecations/propose`)
- **Approve**  -  mark the proposal approved (`POST /governance/deprecations/approve`)
- **List**  -  list deprecation records (`GET /governance/deprecations?namespace=…`)
- **Enforce**  -  set matching **active** rule versions in the store to **inactive** (`POST /governance/deprecations/enforce`)  -  use with RBAC/audit in production

## API (pins and governance)

| Method | Path | Summary |
|--------|------|---------|
| GET | `/governance/environments` | `dev`, `stage`, `prod` |
| GET | `/governance/namespaces` | Distinct namespaces in the current store |
| GET | `/governance/pins` | Optional `?namespace=` filter |
| POST | `/governance/sync-dev` | Body: `namespace`, `rule_handle` |
| POST | `/governance/promote` | Body: `namespace`, `rule_handle`, `from_env`, `to_env` |
| POST | `/governance/deprecations/propose` | Propose a deprecation (body includes `namespace`, `rule_handle`, …) |
| POST | `/governance/deprecations/approve` | Approve a pending deprecation |
| GET | `/governance/deprecations` | List deprecations, optional `?namespace=` |
| POST | `/governance/deprecations/enforce` | Deactivate active versions per approved deprecation in namespace |

## Workbench

**Governance (Phase 4)** in the nav: set namespace and handle, **Sync dev from active**, then **Promote** to stage and to prod, and **Refresh pins**.
