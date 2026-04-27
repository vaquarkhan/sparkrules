# Roadmap

## Phase 3

Focus: **enterprise workbench and packaging**.

- [x] Rule **asset** search and **group** filter (`q`, `group` on `/rules/assets`).
- [x] **Version diff** (unified) for two versions of the same `rule_handle` (`/rules/diff`).
- [x] **Rule pack** export (`/rules/export`) and bulk import (`/rules/import`), format `sparkrules-rulepack-1`.
- [x] Workbench UI: filters, pack download, import, compare.
- [x] Optional: **API key** for mutating API calls when `SPARKRULES_API_KEY` is set (Workbench sends `X-API-Key`; OIDC for shared environments is future work). See [README.md](../README.md#api-run).
- [x] **PyPI / container** release path documented ([PUBLISHING.md](PUBLISHING.md)); trusted publishing and registry push are org-specific. CI **Release build** workflow produces sdist and wheel artifacts.

## Phase 4 (future)

- Multi-project **governance** (namespaces, promotion workflow dev → stage → prod).
- **Benchmarks** in your lakehouse (documented in [BENCHMARKS.md](BENCHMARKS.md) as methodology; numbers come from your runs).
- **Deeper** Drools-style features (CEP, TMS, DMN) only if product scope requires them.

## References

- [FEATURES.md](FEATURES.md) for capability inventory.
- [deploy/README.md](../deploy/README.md) for cloud target notes.
