# ARCHITECTURE.md

# OpenCRO Planning Architecture

The compiler is analogous to a traditional language compiler. Developers edit source code and never edit generated machine code. Likewise, planners edit declarative YAML and never edit generated Linear issues or Warp manifests. The compiler is responsible for translating intent into executable artifacts while preserving traceability and reproducibility.

------------------------------------------------------------------------

# Purpose

OpenCRO is an **agent-operated software company**.

Humans decide **what** should be built.

AI agents decide **how** to build it.

The Planning Compiler converts human planning into deterministic
execution.

The architecture exists to keep planning reproducible, reviewable, and
independent of any execution platform.

The workflow is:

    Planning → Compiler → Operations → Execution

------------------------------------------------------------------------

# System Overview

``` text
Git Planning Repository
        │
        ▼
Planning Compiler
        │
        ├──────────────► Linear
        │                  (Operations Dashboard)
        │
        └──────────────► Warp Manifest
                           (Execution Package)
                                   │
                                   ▼
                             Warp Agent Swarm
                                   │
                                   ▼
                               Artifacts
```

Everything below the planning repository is disposable.

Everything above it is authoritative.

------------------------------------------------------------------------

# Core Principles

## 1. Planning is Code

Planning belongs in Git.

Planning is reviewed.

Planning has history.

Planning can be reproduced.

Never edit generated artifacts.

------------------------------------------------------------------------

## 2. Git is the Source of Truth

The planning repository defines the intended system.

Linear never becomes the authoritative plan.

When the plan changes:

1.  Edit YAML.
2.  Commit.
3.  Compile.
4.  Synchronize.

Never reverse this flow.

------------------------------------------------------------------------

## 3. Linear is the Operations Dashboard

Linear answers:

> What is happening?

It does not answer:

> What should happen?

That answer always lives in Git.

Linear is a projection of the planning repository.

------------------------------------------------------------------------

## 4. Warp Executes

Warp executes compiled work.

Warp does not redesign planning.

Warp does not reprioritize work.

Warp receives executable work packets produced by the compiler.

------------------------------------------------------------------------

## 5. Stable Planning Keys

Every task owns a permanent planning identifier.

Example:

``` text
PF-101
```

Titles may change.

Cycles may change.

Projects may change.

Linear issue IDs may change.

Planning keys never change.

------------------------------------------------------------------------

## 6. Generated Artifacts are Disposable

Nothing under:

``` text
generated/
```

should be edited manually.

Everything generated can be recreated from the planning repository.

------------------------------------------------------------------------

## 7. Relationships are Derived

Planning YAML declares intent.

Example:

``` yaml
depends_on:
  - PF-102
```

The compiler derives the corresponding Linear blocking relationship.

Planning files never contain Linear issue identifiers.

------------------------------------------------------------------------

## 8. Tasks are Contracts

Every task should be executable without asking additional questions.

Each task must define:

-   objective
-   inputs
-   outputs
-   acceptance criteria
-   validation
-   expected artifacts

If an agent cannot execute a task independently, the task is incomplete.

------------------------------------------------------------------------

## 9. Humans Review Decisions

Humans should review decisions with business impact.

Humans should not spend time reviewing mechanical implementation details
that agents can validate automatically.

The objective is not "AI writes code."

The objective is "humans spend attention only where judgment creates
value."

------------------------------------------------------------------------

## 10. Planning is Hierarchical

The planning model is intentionally layered.

``` text
Vision
    ↓
Projects
    ↓
Cycles
    ↓
Tasks
    ↓
Dependency DAG
    ↓
Linear Issues
    ↓
Warp Manifest
    ↓
Execution
    ↓
Artifacts
```

Only the upper layers are edited.

Lower layers are compiled.

------------------------------------------------------------------------

## 11. Artifacts Matter

Every completed task should produce reusable outputs.

Examples:

-   source code
-   migrations
-   schemas
-   generated reports
-   documentation
-   prompt templates
-   tests
-   benchmarks

Completion is measured by artifacts, not by status changes.

------------------------------------------------------------------------

## 12. Small Tasks Win

Large tasks create coordination overhead.

Tasks should be small enough to:

-   execute independently
-   validate automatically
-   unblock downstream work

Dependencies belong in the planning repository, not in human memory.

------------------------------------------------------------------------

## 13. Determinism Over Cleverness

Prefer:

-   explicit dependencies
-   deterministic validation
-   reproducible execution
-   measurable acceptance criteria

over implicit assumptions.

The compiler should remove ambiguity whenever possible.

------------------------------------------------------------------------

## 14. Compiler Responsibilities

The compiler is responsible for:

-   validating planning
-   building the dependency graph
-   rendering Linear issues
-   synchronizing Linear
-   synchronizing relationships
-   compiling Warp execution manifests

The compiler is **not** responsible for executing work.

------------------------------------------------------------------------

## 15. Separation of Concerns

Planning Repository

-   Human-authored
-   Version controlled
-   Long-lived

Linear

-   Operational visibility
-   Current execution state

Warp Manifest

-   Compiled execution package
-   Disposable
-   Regenerated every synchronization

Warp

-   Executes work
-   Produces artifacts

------------------------------------------------------------------------

## 16. Long-Term Vision

Today the compiler targets:

-   Linear
-   Warp

Future targets may include:

-   GitHub Issues
-   Pull Requests
-   Executive dashboards
-   Weekly reports
-   KPI summaries
-   Release notes

without changing the planning repository.

------------------------------------------------------------------------

# Architectural Invariants

These rules should rarely change.

1.  Planning YAML is the only source of truth.
2.  Stable planning keys never change.
3.  Generated artifacts are never edited.
4.  Linear is synchronized, never planned.
5.  Warp consumes compiled manifests.
6.  Relationships are derived from planning.
7.  Planning changes flow from Git to execution, never in reverse.

When implementation details evolve, preserve these invariants whenever
possible.
