# Features

## Core engine

- DRL-style rule parsing and evaluation
- Salience-based priority control
- Agenda group and activation group execution controls
- Explainable outputs with bound data and reason codes

## Authoring formats

- DRL text
- Decision table JSON model
- XLSX decision table import/export

## Execution and runtime

- Single-fact and batch-style execution paths
- Spark dataframe helper paths for partition processing
- Replay metadata model for deterministic re-runs

## Service surfaces

- FastAPI endpoints for health, rules, and simulation
- Python package APIs for parser, compiler, executor, store, and runtime modules

## Observability

- Structured logging helpers
- Metrics endpoint support

## Delivery quality

- Full test suite with unit, property, and integration coverage
- 100% line coverage gate on `src/sre`
