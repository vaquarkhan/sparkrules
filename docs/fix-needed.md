# Requirements Document

## Introduction

The sparkrules engine currently evaluates rules by broadcasting DRL strings to Python workers, re-parsing them per task, and walking the AST row-by-row inside `mapPartitions` — entirely outside Spark's Catalyst optimizer. This feature replaces that anti-pattern with an optimized architecture where rules are first-class structured data: loaded into a RulePack, classified by complexity, and executed via the optimal strategy per rule. The Python path replaces AST walking with compiled closures and alpha-node sharing. The Spark path translates simple rules to Spark SQL expressions (Catalyst-optimized), uses shared alpha columns for medium-complexity rules, and falls back to Python workers with shared alpha networks only for irreducibly complex rules. Cross-path equivalence between Python and Spark execution is a hard requirement.

## Glossary

- **Rule_Pack**: A structured, salience-ordered collection of compiled rules with classification metadata (`is_simple` flag, predicate SQL, action SQL map, alpha hashes). Replaces the raw DRL string as the unit of rule distribution.
- **Alpha_Network**: A discrimination network that flattens AND-chains from rule predicates, deduplicates them by structural hash, and shares evaluation of identical sub-predicates across rules. Built on the existing `compiler/discrimination.py` scaffolding.
- **AST_SQL_Translator**: A compiler pass (`compiler/translator.py`) that converts DRL predicate AST nodes into equivalent Spark SQL expression strings consumable by `pyspark.sql.functions.expr()`.
- **Closure_Compiler**: A compiler pass that converts DRL predicate AST nodes into Python closures at parse time, eliminating per-evaluation `isinstance` dispatch overhead.
- **Strategy_Classifier**: The existing `compiler/classifier.py` module that classifies each rule into an execution strategy (SQL_PUSHDOWN, ALPHA_SHARED, PYTHON_FALLBACK) based on predicate and action complexity.
- **Spark_Rule_Executor**: The top-level Spark executor that dispatches classified rules to the appropriate strategy (A, B, or C) and combines results into a single output DataFrame.
- **Local_Rule_Executor**: The Python-path executor that uses compiled closures and the Alpha_Network for single-fact scoring and batch evaluation without Spark.
- **Strategy_A_SQL_PUSHDOWN**: Execution strategy that translates simple rules to `F.expr()` / `F.when()` Spark SQL expressions, letting Catalyst optimize predicate pushdown, column pruning, and vectorized execution entirely in the JVM.
- **Strategy_B_ALPHA_SHARED**: Execution strategy that evaluates each unique alpha predicate as a `withColumn` boolean, then reconstructs per-rule match results as AND-reductions of those boolean columns.
- **Strategy_C_PYTHON_FALLBACK**: Execution strategy that uses `mapPartitions` with a broadcast-compiled Alpha_Network and Closure_Compiler output for rules that cannot be expressed in Spark SQL.
- **DRL**: The Drools Rule Language variant parsed by `sre.parser.parser`. The grammar supports fact patterns with bindings, comparison/boolean/list operators, and `result.<field> = expr` actions.
- **Catalyst**: Spark's query optimizer that performs predicate pushdown, column pruning, constant folding, and code generation on DataFrame operations.
- **Fact**: A single input record (dict in Python, Row in Spark) against which rules are evaluated.

## Requirements

### Requirement 1: AST-to-SQL Translator

**User Story:** As a platform engineer, I want DRL predicate ASTs to be translated into Spark SQL expression strings, so that simple rules can be pushed down to Catalyst for JVM-native execution without Python worker involvement.

#### Acceptance Criteria

1. WHEN a predicate AST containing only comparison operators (==, !=, <, <=, >, >=), boolean connectives (and, or), negation (not), membership (in, not_in), and literal/identifier leaves is provided, THE AST_SQL_Translator SHALL produce a syntactically valid Spark SQL expression string.
2. WHEN a predicate AST contains the `matches` operator, THE AST_SQL_Translator SHALL translate the operator to the Spark SQL `RLIKE` function.
3. WHEN a predicate AST contains the `contains` operator with string operands, THE AST_SQL_Translator SHALL translate the operator to the Spark SQL `CONTAINS` function or equivalent `LIKE` expression.
4. WHEN a predicate AST contains an identifier referencing a bound variable (e.g. `$t.amount`), THE AST_SQL_Translator SHALL strip the binding prefix and emit the bare column name (e.g. `amount`).
5. IF a predicate AST contains an expression node that has no valid Spark SQL equivalent, THEN THE AST_SQL_Translator SHALL raise a `TranslationError` with the unsupported node type and source location.
6. FOR ALL valid predicate ASTs that the AST_SQL_Translator accepts, translating to SQL then evaluating via Spark `F.expr()` SHALL produce the same boolean result as the reference `evaluate_expr` function on the same fact (round-trip equivalence property).

### Requirement 2: Closure Compiler

**User Story:** As a platform engineer, I want DRL predicate ASTs to be compiled into Python closures at parse time, so that the Python evaluation path avoids per-node `isinstance` dispatch and achieves sub-millisecond latency for 50-rule packs.

#### Acceptance Criteria

1. WHEN a predicate AST is provided, THE Closure_Compiler SHALL produce a Python callable that accepts a fact dict and returns a boolean result.
2. THE Closure_Compiler SHALL support all operators defined in the DRL grammar: ==, !=, <, <=, >, >=, in, not_in, contains, matches, and, or, not.
3. WHEN a compiled closure is evaluated against a fact dict, THE Closure_Compiler output SHALL produce the same boolean result as the reference `evaluate_expr` function on the same inputs (equivalence property).
4. WHEN a runtime error (TypeError, KeyError, ZeroDivisionError) occurs during closure evaluation, THE Closure_Compiler output SHALL degrade to `False` for that sub-expression rather than propagating the exception.
5. THE Closure_Compiler SHALL compile an action AST node into a callable that accepts a fact dict and returns the computed action value.

### Requirement 3: Alpha Network Completion

**User Story:** As a platform engineer, I want the existing alpha-node discrimination network to be completed with closure-compiled evaluation and AND-chain flattening, so that overlapping predicates across rules are evaluated once per fact instead of once per rule.

#### Acceptance Criteria

1. WHEN a list of RuleAst objects is provided, THE Alpha_Network SHALL flatten all AND-chained predicates into individual atomic predicates and deduplicate them by structural hash.
2. THE Alpha_Network SHALL evaluate each unique alpha node at most once per fact, regardless of how many rules reference that predicate (shared evaluation property).
3. WHEN the Alpha_Network evaluates a fact, THE Alpha_Network SHALL produce a per-rule fired/not-fired map that agrees with per-rule evaluation via the reference `evaluate_rule` function (discrimination network equivalence property).
4. THE Alpha_Network SHALL use Closure_Compiler output for alpha-node evaluation instead of the AST-walking `evaluate_expr` function.
5. WHEN a 50-rule pack with typical predicate overlap is provided, THE Alpha_Network SHALL produce a sharing ratio (total predicates / unique alphas) of at least 2.0.

### Requirement 4: Rule Classifier Wiring

**User Story:** As a platform engineer, I want the existing `compiler/classifier.py` to be wired into the execution pipeline with a three-strategy classification (SQL_PUSHDOWN, ALPHA_SHARED, PYTHON_FALLBACK), so that each rule is dispatched to the optimal execution strategy.

#### Acceptance Criteria

1. WHEN a single-fact-type rule has only comparison-operator predicates against literals and side-effect-free literal/identifier actions, THE Strategy_Classifier SHALL classify the rule as SQL_PUSHDOWN.
2. WHEN a single-fact-type rule has column-only predicates (including boolean connectives) but does not qualify for SQL_PUSHDOWN, THE Strategy_Classifier SHALL classify the rule as ALPHA_SHARED.
3. WHEN a rule has multi-fact-type patterns, PASS_2 semantics, or non-translatable expressions, THE Strategy_Classifier SHALL classify the rule as PYTHON_FALLBACK.
4. THE Strategy_Classifier SHALL be a pure function of the RuleAst with no Spark dependency, usable at authoring time for linting and at compile time for dispatch.

### Requirement 5: RulePack Data Structure

**User Story:** As a platform engineer, I want rules represented as a structured RulePack with classification metadata, so that the execution pipeline can dispatch rules by strategy without re-analyzing them at runtime.

#### Acceptance Criteria

1. THE Rule_Pack SHALL store each rule with its name, salience, classified strategy, predicate SQL (for SQL_PUSHDOWN rules), action SQL map, alpha node hashes, and the original RuleAst.
2. THE Rule_Pack SHALL order rules by salience (descending) within each strategy group.
3. WHEN constructed from a list of RuleAst objects, THE Rule_Pack SHALL classify each rule using the Strategy_Classifier and partition rules into SQL_PUSHDOWN, ALPHA_SHARED, and PYTHON_FALLBACK groups.
4. THE Rule_Pack SHALL be serializable via pickle for Spark broadcast distribution.
5. WHEN a Rule_Pack contains SQL_PUSHDOWN rules, THE Rule_Pack SHALL include the pre-translated Spark SQL expression string for each rule's predicate and each action field.

### Requirement 6: SparkRuleExecutor — Strategy A (SQL_PUSHDOWN)

**User Story:** As a data engineer, I want simple rules executed as native Spark SQL expressions inside Catalyst, so that rule evaluation benefits from predicate pushdown, column pruning, and JVM-native vectorized execution with zero Python worker involvement.

#### Acceptance Criteria

1. WHEN a Rule_Pack contains SQL_PUSHDOWN rules, THE Spark_Rule_Executor SHALL add one boolean column per rule to the facts DataFrame using `F.when(F.expr(predicate_sql), F.lit(True)).otherwise(F.lit(False))`.
2. WHEN SQL_PUSHDOWN rules have actions, THE Spark_Rule_Executor SHALL add typed action columns using `F.when(predicate, value)` CASE-WHEN chains ordered by salience.
3. THE Spark_Rule_Executor SHALL combine all SQL_PUSHDOWN rule columns into a single Spark project (no intermediate `collect` or `rdd` conversion).
4. WHEN evaluated on the same facts as the Local_Rule_Executor, THE Spark_Rule_Executor Strategy A output SHALL produce identical fired/not-fired results per rule per fact (cross-path equivalence property).

### Requirement 7: SparkRuleExecutor — Strategy B (ALPHA_SHARED)

**User Story:** As a data engineer, I want rules with overlapping predicates executed via shared alpha-node columns in Spark, so that each unique predicate is evaluated once across all rules that reference it.

#### Acceptance Criteria

1. WHEN a Rule_Pack contains ALPHA_SHARED rules, THE Spark_Rule_Executor SHALL add one boolean `withColumn` per unique alpha predicate using `F.expr(alpha_sql)`.
2. THE Spark_Rule_Executor SHALL reconstruct per-rule match results by AND-reducing the relevant alpha boolean columns for each rule.
3. WHEN ALPHA_SHARED rules have actions, THE Spark_Rule_Executor SHALL add typed action columns using CASE-WHEN chains ordered by salience, consistent with Strategy A output format.
4. WHEN evaluated on the same facts as the Local_Rule_Executor, THE Spark_Rule_Executor Strategy B output SHALL produce identical fired/not-fired results per rule per fact (cross-path equivalence property).

### Requirement 8: SparkRuleExecutor — Strategy C (PYTHON_FALLBACK)

**User Story:** As a data engineer, I want irreducibly complex rules (multi-fact, PASS_2, UDF-dependent) executed via `mapPartitions` with a shared alpha network, so that even the fallback path benefits from predicate sharing.

#### Acceptance Criteria

1. WHEN a Rule_Pack contains PYTHON_FALLBACK rules, THE Spark_Rule_Executor SHALL broadcast the compiled Alpha_Network and Closure_Compiler output (not raw DRL strings) to executors.
2. THE Spark_Rule_Executor SHALL evaluate PYTHON_FALLBACK rules inside `mapPartitions` using the broadcast Alpha_Network for shared predicate evaluation.
3. THE Spark_Rule_Executor SHALL deserialize the broadcast Alpha_Network once per partition task, not once per row.
4. WHEN evaluated on the same facts as the Local_Rule_Executor, THE Spark_Rule_Executor Strategy C output SHALL produce identical fired/not-fired results per rule per fact (cross-path equivalence property).

### Requirement 9: LocalRuleExecutor — Python Path

**User Story:** As an application developer, I want a Python-native rule executor that uses compiled closures and the alpha network for single-fact real-time scoring and batch evaluation, so that the Python path achieves sub-millisecond p99 latency for 50-rule packs.

#### Acceptance Criteria

1. WHEN a single fact dict is provided to the `score` method, THE Local_Rule_Executor SHALL evaluate all rules in the Rule_Pack and return a list of fired rules with their action outputs, ordered by salience.
2. THE Local_Rule_Executor SHALL use the Alpha_Network for shared predicate evaluation and Closure_Compiler output for action computation.
3. WHEN a batch of fact dicts is provided to the `apply` method, THE Local_Rule_Executor SHALL evaluate all rules against all facts and return per-fact results.
4. WHEN evaluated on the same facts and rules as the Spark_Rule_Executor, THE Local_Rule_Executor SHALL produce identical fired/not-fired results and action values per rule per fact (cross-path equivalence property).
5. WHEN evaluating a 50-rule pack against a single fact, THE Local_Rule_Executor SHALL complete in under 1 millisecond at p99 latency.

### Requirement 10: Typed Output Schema

**User Story:** As a data engineer, I want rule execution results as typed Spark struct columns instead of JSON strings, so that downstream queries can access action fields directly without JSON parsing and shuffle bandwidth is reduced.

#### Acceptance Criteria

1. THE Spark_Rule_Executor SHALL output one boolean column per rule indicating fired/not-fired status.
2. THE Spark_Rule_Executor SHALL output typed action columns (e.g. `action_discount` as IntegerType, `action_tier` as StringType) derived from rule action definitions, instead of a single JSON string column.
3. THE Spark_Rule_Executor SHALL add a `fired_any` boolean column that is true when at least one rule fired for the fact.
4. IF the caller provides an explicit action schema, THEN THE Spark_Rule_Executor SHALL use the provided schema for action columns.
5. IF no explicit action schema is provided, THEN THE Spark_Rule_Executor SHALL infer action column types from the Rule_Pack action definitions.

### Requirement 11: Backward-Compatible apply_drl Wrapper

**User Story:** As an existing sparkrules user, I want the current `apply_drl()` API to continue working with a `use_v2=True` flag that defaults to the optimized path, so that I can adopt the new architecture without rewriting my pipeline code.

#### Acceptance Criteria

1. THE apply_drl wrapper SHALL accept a `use_v2` boolean parameter defaulting to `True`.
2. WHEN `use_v2` is True, THE apply_drl wrapper SHALL parse the DRL, build a Rule_Pack, and dispatch to the Spark_Rule_Executor.
3. WHEN `use_v2` is False, THE apply_drl wrapper SHALL execute the original `mapPartitions`-based evaluation path unchanged.
4. WHEN `use_v2` is True, THE apply_drl wrapper SHALL produce output columns that are a superset of the original output schema (fact_id, fired columns are preserved; JSON out_json column is replaced by typed action columns).
5. IF the `use_v2` path encounters a rule that cannot be classified, THEN THE apply_drl wrapper SHALL fall back to Strategy C (PYTHON_FALLBACK) for that rule rather than failing the job.

### Requirement 12: Cross-Path Equivalence Testing

**User Story:** As a platform engineer, I want property-based tests that verify Python and Spark execution paths produce identical results on the same rules and facts, so that path selection is a pure performance decision with no correctness risk.

#### Acceptance Criteria

1. FOR ALL valid Rule_Pack and fact combinations generated by the test harness, THE Local_Rule_Executor and Spark_Rule_Executor SHALL produce the same set of fired rules per fact (cross-path equivalence property).
2. FOR ALL valid Rule_Pack and fact combinations where rules fire, THE Local_Rule_Executor and Spark_Rule_Executor SHALL produce identical action output values per fired rule per fact.
3. THE cross-path equivalence test suite SHALL generate random rule packs with varying predicate complexity (simple comparisons, boolean chains, negation, membership, regex) and random fact dicts with matching field names and value ranges.
4. FOR ALL predicate ASTs accepted by the AST_SQL_Translator, evaluating via `F.expr(translated_sql)` on a Spark DataFrame SHALL produce the same boolean result as `evaluate_expr(ast, bindings)` on the same fact (translator round-trip property).


### Requirement 13: Action Value SQL Translation

**User Story:** As a platform engineer, I want DRL action expressions (e.g. `result.discount = 10`, `result.tier = $t.product`) translated to Spark SQL value expressions, so that Strategy A can build typed CASE WHEN action columns entirely in Catalyst.

#### Acceptance Criteria

1. WHEN an action AST node contains a literal value (integer, float, string, boolean, null), THE AST_SQL_Translator SHALL produce the corresponding Spark SQL literal.
2. WHEN an action AST node references a bound variable field (e.g. `$t.product`), THE AST_SQL_Translator SHALL produce the Spark SQL nested struct access expression (e.g. `t.product`).
3. WHEN an action AST node contains an arithmetic or string expression, THE AST_SQL_Translator SHALL produce the equivalent Spark SQL expression.
4. IF an action AST node contains an expression that cannot be translated to SQL, THEN THE AST_SQL_Translator SHALL mark the owning rule as non-SQL_PUSHDOWN and the rule SHALL fall back to ALPHA_SHARED or PYTHON_FALLBACK.

### Requirement 14: Nested Struct Column Access

**User Story:** As a data engineer, I want the SQL translator to correctly handle Spark nested struct column access (e.g. `t.fico` for a struct column `t` with field `fico`), so that rules work correctly on DataFrames with nested fact schemas.

#### Acceptance Criteria

1. WHEN a DRL identifier `$t.amount` is translated to SQL, THE AST_SQL_Translator SHALL emit `t.amount` (Spark nested struct dot notation), not `amount` (flat column).
2. WHEN a DRL identifier `$t.nested.deep.field` is translated to SQL, THE AST_SQL_Translator SHALL emit `t.nested.deep.field` preserving the full struct path.
3. WHEN the facts DataFrame has a flat schema (no nested struct), THE Spark_Rule_Executor SHALL detect this and adjust column references accordingly (strip the binding prefix entirely).
4. THE Spark_Rule_Executor SHALL validate that all column references in translated SQL exist in the facts DataFrame schema before execution, and raise a clear error if a referenced column is missing.

### Requirement 15: Fact DataFrame Schema Validation

**User Story:** As a data engineer, I want the executor to validate that the facts DataFrame has a proper StructType schema (not MapType) for nested fact columns, so that SQL pushdown produces correct results instead of silent NULLs.

#### Acceptance Criteria

1. WHEN the facts DataFrame contains a column with MapType schema where a StructType is expected by the rules, THE Spark_Rule_Executor SHALL raise a `SchemaValidationError` with a message explaining that the column must be a struct, not a map.
2. WHEN the facts DataFrame has the correct StructType schema, THE Spark_Rule_Executor SHALL proceed with SQL pushdown without modification.
3. THE SchemaValidationError message SHALL include the column name, the expected type (StructType), the actual type (MapType), and a suggestion to use explicit schema when creating the DataFrame.

### Requirement 16: Alpha Column Cleanup

**User Story:** As a data engineer, I want temporary alpha-node boolean columns removed from the final output DataFrame, so that the output schema is clean and contains only rule-result and action columns.

#### Acceptance Criteria

1. WHEN Strategy B (ALPHA_SHARED) adds temporary `_a_<hash>` boolean columns during evaluation, THE Spark_Rule_Executor SHALL drop all such columns before returning the result DataFrame.
2. THE final output DataFrame SHALL contain only: original fact columns, `r_<rule_name>` boolean columns, `action_<field>` typed columns, and `fired_any` boolean column.

### Requirement 17: Cross-Strategy Salience Resolution

**User Story:** As a data engineer, I want action output to respect salience ordering across all three execution strategies, so that the highest-salience firing rule's action wins regardless of which strategy evaluated it.

#### Acceptance Criteria

1. WHEN rules from different strategies (A, B, C) fire on the same fact, THE Spark_Rule_Executor SHALL resolve action field conflicts by selecting the value from the highest-salience firing rule across all strategies.
2. THE Spark_Rule_Executor SHALL merge action columns from all three strategies into a single set of `action_<field>` columns using a salience-ordered CASE WHEN chain that spans all strategies.
3. WHEN only one strategy is active (e.g. all rules are SQL_PUSHDOWN), THE Spark_Rule_Executor SHALL skip the cross-strategy merge step.

### Requirement 18: Performance Targets

**User Story:** As a product owner, I want explicit performance targets for the optimized executor, so that the implementation can be validated against measured benchmarks.

#### Acceptance Criteria

1. WHEN evaluating a 50-rule lending pack against a single fact, THE Local_Rule_Executor SHALL complete in under 500 microseconds at p99 latency (target: 240µs measured in prototype).
2. WHEN evaluating a 50-rule lending pack against 100,000 facts on Spark local[4], THE Spark_Rule_Executor with Strategy A SHALL complete in under 10 seconds wall-clock (target: 4.72s measured in prototype).
3. WHEN evaluating a 50-rule lending pack against 100,000 facts on Spark local[4], THE Spark_Rule_Executor with auto-classification SHALL achieve at least 20,000 rows/sec throughput (target: 38,674 rows/sec measured in prototype).
4. THE optimized executor SHALL achieve at least 10x speedup over the current `apply_drl(use_v2=False)` path on the same workload and hardware.

### Requirement 19: iter_rule_rows Optimization

**User Story:** As a developer using the no-JVM Spark path, I want `iter_rule_rows` to also benefit from compiled closures and alpha sharing, so that the pure-Python row iterator is faster without requiring a SparkSession.

#### Acceptance Criteria

1. WHEN `iter_rule_rows` is called with a multi-rule DRL, THE function SHALL build an Alpha_Network and use Closure_Compiler output for evaluation instead of the AST-walking `run_rule_chain`.
2. WHEN `iter_rule_rows` is called with a single-rule DRL, THE function SHALL use a compiled closure for that rule's predicate instead of `evaluate_rule` with AST walking.
3. THE optimized `iter_rule_rows` SHALL produce identical `(fact_id, fired, out_json)` tuples as the current implementation for the same inputs (backward compatibility property).
4. THE optimized `iter_rule_rows` SHALL achieve at least 5x throughput improvement over the current implementation on a 50-rule pack.


### Requirement 20: Pickle-Safe Broadcast for Strategy C

**User Story:** As a data engineer, I want the Python fallback strategy to broadcast rule evaluation artifacts to Spark workers without pickle failures on compiled closures, so that Strategy C works reliably on real Spark clusters.

#### Acceptance Criteria

1. WHEN the Spark_Rule_Executor broadcasts artifacts for Strategy C, THE broadcast payload SHALL NOT contain Python lambda or closure objects (which fail `pickle.dumps`).
2. THE Spark_Rule_Executor SHALL broadcast either the raw DRL string or a pickle-safe serialized AST representation, and reconstruct the Alpha_Network + Closure_Compiler output inside each worker task.
3. THE Alpha_Network and Closure_Compiler reconstruction SHALL happen once per partition task (not once per row), using the broadcast DRL or AST as input.
4. THE broadcast payload size SHALL be proportional to the DRL text size (typically <100 KB for 1000-rule packs), not proportional to the number of compiled closures.

### Requirement 21: Regex Compatibility Between Python and Spark

**User Story:** As a platform engineer, I want rules using the `matches` operator to produce identical results on both the Python path (Python `re` module) and the Spark path (Spark `RLIKE` / Java regex), so that cross-path equivalence holds for regex-containing rules.

#### Acceptance Criteria

1. THE AST_SQL_Translator SHALL document which Python regex features are NOT supported by Spark RLIKE (e.g. look-ahead `(?=...)`, look-behind `(?<=...)`, atomic groups, possessive quantifiers).
2. WHEN a predicate AST contains a `matches` operator with a regex pattern that uses Python-only features, THE Strategy_Classifier SHALL classify the rule as PYTHON_FALLBACK (not SQL_PUSHDOWN).
3. THE cross-path equivalence test suite (Req 12) SHALL include test cases with regex patterns that exercise common regex features (character classes, quantifiers, anchors, alternation, case-insensitive flags) and verify identical results on both paths.
4. WHEN a regex pattern uses the `(?i)` inline flag (case-insensitive), THE AST_SQL_Translator SHALL translate it to the Spark-compatible equivalent (prepend `(?i)` which Spark RLIKE supports).

### Requirement 22: Pandas Batch Evaluation for LocalRuleExecutor

**User Story:** As a data scientist, I want the LocalRuleExecutor to evaluate rules against a pandas DataFrame using vectorized operations (pandas.eval / numexpr) for simple rules, so that batch evaluation on a single machine achieves 100k+ rows/sec without Spark.

#### Acceptance Criteria

1. WHEN a pandas DataFrame is provided to the `apply_pandas` method, THE Local_Rule_Executor SHALL evaluate SQL_PUSHDOWN rules using `pandas.eval()` with the translated predicate SQL (adapted for pandas syntax).
2. WHEN a pandas DataFrame is provided, THE Local_Rule_Executor SHALL evaluate PYTHON_FALLBACK rules using row-wise closure application via `DataFrame.apply()`.
3. THE `apply_pandas` method SHALL return a pandas DataFrame with boolean columns per rule (`r_<rule_name>`) and typed action columns (`action_<field>`), consistent with the Spark output schema.
4. WHEN evaluating a 50-rule pack against 100,000 rows, THE `apply_pandas` method SHALL complete in under 30 seconds on a single thread (target: vectorized simple rules at 100k+ rows/sec).

### Requirement 23: Hot-Swap Rule Reloading

**User Story:** As a platform engineer running a long-lived Spark Structured Streaming job, I want to reload rules without restarting the SparkSession, so that rule changes take effect within the current job without downtime.

#### Acceptance Criteria

1. THE Spark_Rule_Executor SHALL expose a `refresh_rules(drl: str)` method that rebuilds the Rule_Pack from new DRL and replaces the cached rule state.
2. WHEN `refresh_rules` is called, THE Spark_Rule_Executor SHALL unpersist any cached rule DataFrames and rebuild the Rule_Pack, Alpha_Network, and strategy classification from the new DRL.
3. THE `refresh_rules` method SHALL NOT require stopping or restarting the SparkSession.
4. AFTER `refresh_rules` is called, subsequent calls to `apply()` SHALL use the new rules immediately.
5. THE Local_Rule_Executor SHALL expose an equivalent `refresh_rules(drl: str)` method with the same semantics.

### Requirement 24: Agenda Group and Activation Group Semantics at Spark Scale

**User Story:** As a data engineer, I want `agenda_group` and `activation_group` DRL semantics to work correctly in the optimized Spark executor, so that rule ordering and mutual-exclusion behavior is preserved when rules run inside Catalyst.

#### Acceptance Criteria

1. WHEN multiple rules share the same `activation_group`, THE Spark_Rule_Executor SHALL ensure that at most one rule from that group fires per fact (XOR semantics), with the highest-salience rule winning.
2. WHEN rules have different `agenda_group` values, THE Spark_Rule_Executor SHALL evaluate groups in the order defined by the chain execution policy (or salience-ordered if no explicit group ordering).
3. WHEN a rule has `stop_on_fire = true` and fires, THE Spark_Rule_Executor SHALL suppress evaluation of all lower-salience rules for that fact (chain halt semantics).
4. THE activation_group XOR and stop_on_fire semantics SHALL produce identical results on both the Local_Rule_Executor and Spark_Rule_Executor paths (cross-path equivalence for chain semantics).
5. FOR Strategy A (SQL_PUSHDOWN), activation_group XOR SHALL be implemented as a CASE WHEN chain where only the first (highest-salience) matching rule in the group produces output.


### Requirement 25: FactView with __slots__ for Zero-Copy Field Access

**User Story:** As a platform engineer, I want fact field values accessed via Python `__slots__` attribute access instead of `dict.get()` calls, so that per-alpha evaluation overhead drops from ~2.5µs to ~0.5µs and the 50-rule single-fact latency target drops below 50µs p99.

#### Acceptance Criteria

1. THE ReteNetwork SHALL dynamically generate a FactView class with `__slots__` containing exactly the fields referenced by the rule pack (no unused fields).
2. THE ReteNetwork SHALL construct ONE FactView instance per fact evaluation, populating all field attributes from the fact dict in a single pass.
3. ALL alpha and beta evaluation closures SHALL access fact values via `getattr(fv, attr)` on the FactView instance, NOT via `dict.get()`.
4. THE FactView construction + field population SHALL complete in under 5 microseconds for a fact with 10 fields.
5. FOR membership predicates (`in`, `not in`), THE ReteNetwork SHALL pre-build `frozenset` objects at compile time and use O(1) `in` checks at evaluation time.

### Requirement 26: Range-Merged Alpha Nodes

**User Story:** As a platform engineer, I want range predicates on the same field (e.g. `fico >= 620`, `fico >= 630`, `fico >= 640`) merged into a single field-value extraction, so that the number of unique alpha evaluations drops from O(predicates) to O(fields) and the 1000-rule single-fact latency target drops below 200µs p99.

#### Acceptance Criteria

1. WHEN multiple rules reference range predicates (>=, <=, >, <) on the same field, THE ReteNetwork SHALL extract the field value ONCE and let each rule's beta node compare against its own threshold.
2. THE ReteNetwork alpha layer SHALL have at most one value-extraction node per unique field path, regardless of how many rules reference that field with different thresholds.
3. WHEN a 50-rule pack references 6 unique fields, THE ReteNetwork SHALL have at most 6 alpha value-extraction nodes (plus additional nodes for non-range predicates like equality and membership).
4. THE beta-node threshold checks SHALL be compiled as direct comparison closures using the extracted field values, with short-circuit evaluation (stop at first failing predicate).
5. WHEN evaluating a 50-rule pack with 6 unique fields against a single fact, THE ReteNetwork SHALL complete in under 50 microseconds at p99 latency (target: ~15µs measured projection).
6. WHEN evaluating a 1000-rule pack against a single fact, THE ReteNetwork SHALL complete in under 200 microseconds at p99 latency.


### Requirement 27: Native Extension for Hot-Loop Evaluation (Cython/Rust via PyO3)

**User Story:** As a platform engineer, I want the per-fact rule evaluation hot loop compiled to native code via Cython or Rust (PyO3), so that the Python path closes the remaining 12-16x per-core latency gap with Drools' JVM bytecode and achieves <20µs p99 for 50-rule packs.

#### Acceptance Criteria

1. THE native extension SHALL implement the FactView construction, alpha field extraction, and beta threshold checks as compiled native code (Cython `.pyx` or Rust via PyO3), callable from Python with zero-copy fact passing.
2. THE native extension SHALL accept a fact dict from Python, extract field values into a native struct (equivalent to FactView with `__slots__`), and evaluate all beta checks in a single native function call — returning a `dict[str, bool]` of rule fires.
3. WHEN evaluating a 50-rule lending pack against a single fact, THE native extension SHALL complete in under 20 microseconds at p99 latency (target: Drools parity at ~10µs, with Python call overhead ~5-10µs).
4. WHEN evaluating a 1000-rule pack against a single fact, THE native extension SHALL complete in under 50 microseconds at p99 latency.
5. THE native extension SHALL be an OPTIONAL dependency — if the compiled `.so`/`.pyd` is not installed, THE executor SHALL fall back to the pure-Python Rete path (Req 25-26) transparently with no API change.
6. THE native extension SHALL be distributable as a pre-built wheel for Linux x86_64, macOS arm64, and Windows x86_64 via PyPI (`pip install sparkrules[native]`).
7. THE native extension SHALL produce identical fired/not-fired results as the pure-Python Rete path for the same rules and facts (native-Python equivalence property).
8. THE native extension build SHALL be integrated into CI with cross-platform wheel builds (cibuildwheel or maturin) and tested against the cross-path equivalence suite (Req 12).

### Requirement 28: Native Extension for Spark Strategy C Workers

**User Story:** As a data engineer, I want the Python fallback strategy (Strategy C) to use the native extension inside Spark Python workers when available, so that even the fallback path achieves near-JVM-native throughput.

#### Acceptance Criteria

1. WHEN the native extension is installed in the Spark Python worker environment, THE Strategy C mapPartitions function SHALL use the native evaluation path instead of the pure-Python Rete path.
2. WHEN the native extension is NOT installed in the worker environment, THE Strategy C mapPartitions function SHALL fall back to the pure-Python Rete path without error.
3. THE native extension SHALL be broadcast-safe — the compiled rule pack representation used by the native extension SHALL be serializable via pickle or a custom binary format for Spark broadcast.
4. WHEN using the native extension in Strategy C, THE per-row evaluation overhead SHALL be under 5 microseconds (target: 2-3µs per row for a 50-rule pack), bringing Strategy C throughput to within 2x of Strategy A (SQL pushdown).

### Requirement 29: Native Extension Compilation Pipeline

**User Story:** As a platform engineer, I want the rule pack compiled to a native evaluation function at RulePack build time, so that the native extension does not re-parse or re-compile rules at evaluation time.

#### Acceptance Criteria

1. THE RulePack build step SHALL compile the beta-check closures into a native evaluation function (Cython-generated C code or Rust function) that accepts a flat array of field values and returns a boolean array of rule fires.
2. THE native compilation SHALL happen ONCE at RulePack construction time (not per-fact or per-partition).
3. THE compiled native function SHALL be cacheable on disk (e.g. as a `.so`/`.pyd` keyed by DRL content hash) so that repeated runs with the same rule pack skip recompilation.
4. IF native compilation fails (missing compiler, unsupported platform), THE RulePack SHALL fall back to the pure-Python Rete path and log a warning.
5. THE native compilation time SHALL be under 5 seconds for a 1000-rule pack on a standard developer machine.
