# Roadmap

## Phase 3

Focus: **enterprise workbench and packaging**.

- [x] Rule **asset** search and **group** filter (`q`, `group` on `/rules/assets`).
- [x] **Version diff** (unified) for two versions of the same `rule_handle` (`/rules/diff`).
- [x] **Rule pack** export (`/rules/export`) and bulk import (`/rules/import`), format `sparkrules-rulepack-1`.
- [x] Workbench UI: filters, pack download, import, compare.
- [x] Optional: **API key** when `SPARKRULES_API_KEY` is set: mutating methods plus **sensitive GET**s (`/rules/…` data, `/system/deployment`, `/governance/…`); public `GET /health`, OpenAPI, `OPTIONS`, and static `/workbench/…`. **OIDC** / browser SSO is not in-repo (use a reverse proxy or network policy). See [README.md](../README.md#api-run).
- [x] **PyPI / container** release path documented ([PUBLISHING.md](PUBLISHING.md)); trusted publishing and registry push are org-specific. CI **Release build** workflow produces sdist and wheel artifacts.

## Recent additions (shipped; see [FEATURES.md](FEATURES.md))

- [x] **Workbench:** **Monaco** DRL editor, **Validate** + **LSP** (`/rules/validate`, `/ide/lsp/analyze`), light/dark theme
- [x] **Simulations:** **counterfactual** (`/simulations/counterfactual`), **chain** (`/simulations/chain`) with DRL per-rule `stop_on_fire` and request/engine `stop_on_decline` policy
- [x] **Debug:** time-travel **capture** / **replay** (`/debug/time-travel/*`) backed by a `debug_runs` table
- [x] **Governance:** **deprecations**  -  propose, approve, list, **enforce** (deactivate version) under `/governance/deprecations*`
- [x] **Executor:** local `SQL_JOIN` / list-binding **Cartesian** expansion for multi-pattern rules (when enabled)
- [x] **Store:** **append-only** option on Iceberg-like tables for selected internal use
- [x] **Client / CLI:** `SparkRulesClient` and `sparkrules-cli` **counterfactual** and time-travel / deprecation **enforce** helpers
- [x] **Tests:** 100% **line** coverage on `src/sparkrules` via `tests/unit/`

## Phase 4 (complete)

- [x] Multi-project **governance**: rule **`namespace`**, in-memory **environment pins** (`dev` / `stage` / `prod`), **sync dev** and **adjacent promote** API + Workbench. See [GOVERNANCE.md](GOVERNANCE.md).
- [x] **Lakehouse benchmarks**  -  end-to-end checklist and methodology in [BENCHMARKS.md](BENCHMARKS.md#phase-4--lakehouse-benchmarks). Numbers remain cluster-specific; the repo provides harnesses and documentation.
- [x] **CEP, TMS, full DMN** (Drools-style depth)  -  **deferred**; minimal DMN table XML + KIE-shaped REST exist; CEP/TMS/full FEEL+TCK remain out of scope until requested.

## References

- [FEATURES.md](FEATURES.md) for capability inventory.
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for **architecture scope** and extension points (identity, Spark, Workbench, performance).
- [deploy/README.md](../deploy/README.md) for cloud target notes.
