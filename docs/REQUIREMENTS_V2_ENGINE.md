# Requirements: V2 Optimized Rule Engine

> This document defines the requirements for the next-generation SparkRules execution engine.
> Status: **Planning** — foundation modules in progress.

## Overview

The V2 engine replaces the current AST-walking evaluation with an optimized architecture:
- **Closure Compiler** — DRL predicates compiled to Python closures at parse time
- **Alpha Network** — shared predicate evaluation across rules (Rete-style)
- **AST-to-SQL Translator** — simple rules pushed down to Spark Catalyst
- **Three execution strategies** — SQL_PUSHDOWN, ALPHA_SHARED, PYTHON_FALLBACK
- **Cross-path equivalence** — Python and Spark paths produce identical results

## Requirements Summary

| Req | Title | Priority | Status |
|-----|-------|----------|--------|
| 1 | AST-to-SQL Translator | High | In Progress |
| 2 | Closure Compiler | High | In Progress |
| 3 | Alpha Network Completion | High | In Progress |
| 4 | Rule Classifier Wiring | High | In Progress |
| 5 | RulePack Data Structure | High | In Progress |
| 6 | Strategy A: SQL_PUSHDOWN | High | Planned |
| 7 | Strategy B: ALPHA_SHARED | High | Planned |
| 8 | Strategy C: PYTHON_FALLBACK | High | Planned |
| 9 | LocalRuleExecutor | High | Planned |
| 10 | Typed Output Schema | Medium | Planned |
| 11 | Backward-Compatible apply_drl | High | Planned |
| 12 | Cross-Path Equivalence Testing | High | Planned |
| 13 | Action Value SQL Translation | Medium | Planned |
| 14 | Nested Struct Column Access | Medium | Planned |
| 15 | Schema Validation | Medium | Planned |
| 16 | Alpha Column Cleanup | Low | Planned |
| 17 | Cross-Strategy Salience | Medium | Planned |
| 18 | Performance Targets | High | Planned |
| 19 | iter_rule_rows Optimization | Medium | Planned |
| 20 | Pickle-Safe Broadcast | Medium | Planned |
| 21 | Regex Compatibility | Low | Planned |
| 22 | Pandas Batch Evaluation | Medium | Planned |
| 23 | Hot-Swap Rule Reloading | Medium | Planned |
| 24 | Agenda/Activation Group Semantics | Medium | Planned |
| 25 | FactView with __slots__ | Medium | Planned |
| 26 | Range-Merged Alpha Nodes | Medium | Planned |
| 27 | Native Extension (Cython/Rust) | Low | Future |
| 28 | Native Extension for Strategy C | Low | Future |
| 29 | Native Compilation Pipeline | Low | Future |

Full requirement details are maintained in the internal planning document.
