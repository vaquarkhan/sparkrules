# AGENTS.md

> Context file for AI coding agents (Codex, Claude Code, Cursor, Copilot, Kiro, etc.)

## Project overview

SparkRules is a Python business rule engine using Drools-style DRL syntax. It evaluates structured facts against rules and returns explainable results. Python-first, optionally scales to Spark clusters.

- **Package:** `sparkrules` (import as `from sparkrules.executor import RuleExecutor`)
- **Python:** 3.11+
- **License:** Apache 2.0

## Dev environment

```bash
python -m pip install -e ".[test]"
```

## Testing

```bash
# Full suite (521 tests, 100% coverage gate)
pytest tests/ -q

# Unit tests only (fast)
pytest tests/unit/ -q

# With coverage
pytest tests/unit/ --cov=sparkrules --cov-report=term

# Performance benchmarks (opt-in)
pytest tests/perf -m perf -q
```

Coverage is enforced at 100% on `src/sparkrules/` via `fail_under=100` in `pyproject.toml`.

## Linting

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

## Code layout

```
src/sparkrules/           # main package
  parser/                 # DRL lexer, parser, AST, pretty-printer
  compiler/               # rule classification, discrimination nets, evaluator
  executor/               # agenda, rule execution engine
  runtime/                # batch, streaming, replay, config, export
  api/                    # FastAPI app, schemas, security, workbench UI
  store/                  # metadata store (in_memory, duckdb, iceberg, postgres)
  sim/                    # simulator (shadow, coverage, counterfactual, chain)
  governance/             # deprecation, promotion pins
  model/                  # rule, decision table, template models
  spark/                  # optional PySpark integration (apply_drl)
  client/                 # Python SDK (SreClient)
  tools/                  # CLI (sparkrules-cli)
  ide/                    # LSP diagnostics
  dq/                     # data quality engine
  obs/                    # logging, metrics, health
tests/
  unit/                   # ~480 unit tests
  property/               # Hypothesis property-based tests
  integration/            # end-to-end use case tests
  perf/                   # opt-in benchmarks
  spark/                  # PySpark tests (need JVM)
```

## Key patterns

### Evaluate a rule
```python
from sparkrules.executor import RuleExecutor

result = RuleExecutor().run(
    {"amount": 1500},
    'rule "high" when $f : Fact( amount > 1000 ) then result.risk = "high"; end',
)
# result.fired, result.action_output, result.bound_fields
```

### Parse DRL
```python
from sparkrules.parser import parse, parse_rules
ast = parse('rule "r" when $f : T( x > 1 ) then result.y = 2; end')
```

### Decision table
```python
from sparkrules.model.decision_table import (
    DecisionTable, InputColumn, OutputColumn, Row,
    ColumnType, HitPolicy, evaluate_decision_table,
)
```

### Start the API
```bash
pip install sparkrules[api]
python -m uvicorn sparkrules.api.app:create_app --factory --port 8042
```

### Spark integration
```python
# pip install sparkrules[spark]
from sparkrules.spark import apply_drl
result_df = apply_drl(df, drl)  # distributed via mapPartitions
```

## DRL syntax

```
rule "name"
  salience <int>                          # priority (higher = first)
  agenda-group "<name>"                   # group rules into stages
  activation-group "<name>"               # XOR: only one fires
  reason_codes ["CODE1", "CODE2"]         # attach codes to output
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

- Keep changes focused; pair behavior changes with tests
- Run `ruff check` and `pytest tests/unit/ -q` before committing
- Update docs in `docs/` when behavior changes
