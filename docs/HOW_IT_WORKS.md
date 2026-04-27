# How SparkRules works

## High-level flow

1. Author rules in DRL or decision-table form.
2. Parse and validate rule syntax and references.
3. Compile rules into execution-ready structures.
4. Evaluate facts and produce rule results.
5. Persist and/or emit run metadata and result data.
6. Replay by reusing pinned run context and rule versions.

## Main components

- **Parser**: converts DRL text into AST structures.
- **Compiler**: prepares rule packages and strategy metadata.
- **Executor**: evaluates compiled logic against facts.
- **Metadata store**: versions rules and resolves active sets.
- **Runtime helpers**: replay, cache, streaming support primitives.
- **API layer**: exposes operational endpoints.

## Execution controls

- Salience: prioritizes competing activations.
- Agenda groups: scope which rules run in a stage.
- Activation groups: XOR behavior for competing rules.

## Data and output model

- Rule evaluation returns fired state, bound field values, and action outputs.
- Runtime records include run identifiers and reproducibility metadata.
- Store and runtime APIs are designed for deterministic behavior under replay.
