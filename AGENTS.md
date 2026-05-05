# AGENTS.md

> Context file for AI coding agents (Codex, Claude Code, Cursor, Copilot, Kiro, etc.)

## Project overview

SparkRules is a Python business rule engine using Drools-style DRL syntax. It evaluates structured facts against rules and returns explainable results. Python-first, optionally scales to Spark clusters.

- **Package:** `sparkrules` (import as `from sparkrules.executor import RuleExecutor`)
- **Python:** 3.11+
- **License:** Apache 2.0
- **Tests:** 840+ (100% line coverage enforced)

## Dev environment

```bash
python -m pip install -e ".[test]"
```

## Testing — CRITICAL RULES

**Every change MUST pass these gates before committing:**

```bash
# 1. Run unit tests (REQUIRED before every commit)
pytest tests/unit/ -q

# 2. Run with coverage (REQUIRED — must be 100%)
pytest tests/unit/ --cov=sparkrules --cov-report=term
# fail_under=100 is enforced in pyproject.toml

# 3. Full suite including property + integration
pytest tests/ -q
```

### Coverage rules

- **100% line coverage is enforced.** `pyproject.toml` has `fail_under = 100`.
- If you add new code, you MUST add tests that cover every line.
- If a line is genuinely unreachable (defensive guard, Spark-only path), use `# pragma: no cover`.
- Do NOT use `# pragma: no cover` on reachable code — write a test instead.
- Coverage is measured on `src/sparkrules/` only, not on tests.

### Test file conventions

- Unit tests go in `tests/unit/test_<module>.py`
- Property tests go in `tests/property/` using Hypothesis with `max_examples=100`
- Integration tests go in `tests/integration/`
- Performance benchmarks go in `tests/perf/` with `@pytest.mark.perf`
- Spark tests requiring JVM go in `tests/spark/`

### Writing good tests

```python
# DO: test the public API, not internals
def test_rule_executor_fires_on_match() -> None:
    result = RuleExecutor().run({"t": {"x": 10}}, 'rule "r" when $t : T ( $t.x > 5 ) then result.ok = true; end')
    assert result.fired is True
    assert result.action_output == {"ok": True}

# DO: test edge cases and error paths
def test_rule_executor_error_degrades_gracefully() -> None:
    result = RuleExecutor().run({"t": {}}, 'rule "r" when $t : T ( $t.missing > 5 ) then end')
    assert result.fired is False  # missing field -> no fire, no crash

# DO: use type annotations on all test functions
def test_example() -> None:
    ...

# DON'T: skip coverage with pragma unless truly unreachable
# DON'T: use print() in tests — use assertions
# DON'T: leave temporary test files in the repo
```

## Linting — REQUIRED before commit

```bash
# Both must pass with zero errors
ruff check src/ tests/
ruff format --check src/ tests/

# Auto-fix lint issues
ruff check src/ tests/ --fix
ruff format src/ tests/
```

### Ruff configuration (pyproject.toml)

- Line length: 100
- Target: Python 3.11
- E741 ignored globally (allows `l` as variable name in parser)
- F401/F841 ignored in `__init__.py` and test files

## Code layout

```
src/sparkrules/
  parser/                 # DRL lexer, parser, AST, pretty-printer
  compiler/               # translator, closure, alpha_network, rete, rulepack, classifier
  executor/               # rule_executor, local_executor, pandas_executor, adverse_action, agenda
  runtime/                # batch, streaming, replay, config, export, rule_chain, two_pass
  api/                    # FastAPI app, schemas, security, kie, workbench UI
  store/                  # metadata_store, backends, sql_metadata (DuckDB/Postgres)
  sim/                    # simulator (shadow, coverage, counterfactual, chain)
  spark/                  # dataframe (apply_drl), executor (SparkRuleExecutor)
  governance/             # deprecation, promotion pins, registry
  dq/                     # engine (checks), profile (statistical profiling)
  export/                 # opa (Rego export)
  compliance/             # adverse_action (ECOA/FCRA/GDPR)
  dmn/                    # minimal_xml (DMN 1.3 import)
  integrations/           # feast_client, tecton_client
  policy/                 # opa_client, ranger_client
  model/                  # rule, decision_table, rule_template
  client/                 # SDK (SreClient)
  tools/                  # CLI (sparkrules-cli)
  ide/                    # LSP diagnostics
  obs/                    # logging, metrics, health
  transport/              # broadcaster
  connect/                # server
  ai/                     # service, openai_provider
  native/                 # optional Rust bridge (sparkrules_native PyO3)
tests/
  unit/                   # ~700 unit tests
  property/               # Hypothesis property-based tests (P01-P38, P61)
  integration/            # end-to-end use case tests
  perf/                   # opt-in benchmarks
  spark/                  # PySpark tests (need JVM)
```

## Key patterns

### V2 engine (preferred for new code)

```python
# LocalRuleExecutor — fast Python-native scoring
from sparkrules.executor.local_executor import LocalRuleExecutor

executor = LocalRuleExecutor.from_drl(drl)
result = executor.score({"t": {"amount": 1500}})
# result.fired_any, result.merged_actions, result.fires

# Batch evaluation
results = executor.apply([fact1, fact2, fact3])

# Hot-swap rules without restart
executor.refresh_rules(new_drl)
```

### Native Rust accelerator (optional)

```python
# NativeRuleExecutor — same fact dict as LocalRuleExecutor; Tier-1 FFI uses JSON strings per row (fastest shipped path vs PyDict↔Value bridge); requires wheel or maturin build
from sparkrules.native.executor import NativeRuleExecutor

native = NativeRuleExecutor.from_drl(drl)
result = native.score({"t": {"amount": 1500}})
# Parity target: same fires / merged_actions as LocalRuleExecutor.score()
```

Install: `pip install sparkrules[native]` (PyPI: `sparkrules-native`) or `maturin develop --release` under `sparkrules_native/`. Maintainer checks: `scripts/verify_native.sh` / `verify_native.ps1`. See [docs/NATIVE_TIER1.md](docs/NATIVE_TIER1.md).

### RulePack classification

```python
from sparkrules.compiler.rulepack import RulePack, Strategy

pack = RulePack.from_drl(drl)
for rule in pack.rules:
    print(f"{rule.name}: {rule.strategy.name}")
    # SQL_PUSHDOWN — Catalyst-optimized
    # ALPHA_SHARED — shared boolean columns
    # PYTHON_FALLBACK — mapPartitions with closures
```

### Legacy executor (still works)

```python
from sparkrules.executor import RuleExecutor

result = RuleExecutor().run(
    {"amount": 1500},
    'rule "high" when $f : Fact( amount > 1000 ) then result.risk = "high"; end',
)
```

### Parse DRL

```python
from sparkrules.parser import parse, parse_rules
ast = parse('rule "r" when $f : T( $f.x > 1 ) then result.y = 2; end')
rules = parse_rules(multi_rule_drl)  # returns list[RuleAst]
# parse() and parse_rules() are LRU-cached (256 entries)
```

### Decision table

```python
from sparkrules.model.decision_table import (
    DecisionTable, InputColumn, OutputColumn, Row,
    ColumnType, HitPolicy, evaluate_decision_table,
)
```

### Adverse-action notices (regulatory)

```python
from sparkrules.executor import build_adverse_action_notice

notice = build_adverse_action_notice(results, decision="decline", fact_id="app-123")
# notice.principal_reasons — up to 4 per ECOA
# notice.all_reason_codes — full list
```

### Data profiling

```python
from sparkrules.dq import profile_rows

profile = profile_rows(batch_of_facts)
# profile.fields[0].completeness, .uniqueness, .numeric_stats
```

### OPA/Rego export

```python
from sparkrules.export.opa import export_to_rego

rego = export_to_rego(drl, package_name="myorg.policy")
```

### Start the API

```bash
pip install sparkrules[api]
python -m uvicorn sparkrules.api.app:create_app --factory --port 8042
```

### Spark integration

```python
from sparkrules.spark import apply_drl

# V2 (default): typed output columns, 3-strategy dispatch
result_df = apply_drl(df, drl, use_v2=True)

# V1 (legacy): JSON output column
result_df = apply_drl(df, drl, use_v2=False)
```

## DRL syntax

```
rule "name"
  salience <int>                          # priority (higher = first)
  agenda-group "<name>"                   # group rules into stages
  activation-group "<name>"               # XOR: only one fires
  reason_codes ["CODE1", "CODE2"]         # attach codes to output
  stop_on_fire true                       # halt chain if this fires
  when
    $binding : FactType( field > value )  # pattern match
  then
    result.field = expression;            # set output
end
```

Operators: `==`, `!=`, `>`, `>=`, `<`, `<=`, `in`, `not in`, `contains`, `matches`, `and`, `or`, `not`

## Install extras

```bash
pip install sparkrules          # core engine
pip install sparkrules[api]     # + FastAPI server and Workbench
pip install sparkrules[spark]   # + PySpark
pip install sparkrules[all]     # everything
pip install sparkrules[test]    # dev/test dependencies
```

## PR conventions

- **Every PR must pass:** `ruff check`, `ruff format --check`, `pytest tests/unit/`, 100% coverage
- Keep changes focused; pair behavior changes with tests
- Update docs in `docs/` when behavior or API changes
- Update `CHANGELOG.md` for user-facing changes
- Do not commit `__pycache__/`, `.vscode/`, or temporary files
- Use conventional commit messages: `feat:`, `fix:`, `docs:`, `test:`, `chore:`
- **Do not** add Cursor (or other vendor) footers to commits: no `Co-authored-by: Cursor`, no `Made-with: Cursor`, no similar trailers unless the maintainer explicitly asks. Turn off Cursor **Agent → Attribution** in settings; see `.cursor/rules/git-commit-no-cursor.mdc` and `CONTRIBUTING.md`.

## Architecture decisions

- **Python-first, Spark-ready:** core engine runs without Spark; Spark is opt-in
- **V2 engine:** closure compiler + alpha network replaces AST walking
- **Three strategies:** SQL_PUSHDOWN (Catalyst), ALPHA_SHARED (boolean columns), PYTHON_FALLBACK (mapPartitions)
- **100% coverage:** no exceptions; use `# pragma: no cover` only for genuinely unreachable code
- **LRU parse caching:** `parse()` and `parse_rules()` cache by DRL text (256 entries)
- **Honest scope:** `docs/KNOWN_LIMITATIONS.md` documents what is and isn't production-ready
