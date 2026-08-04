# Compiler-Implementation-Task.md

# OpenCRO Planning Compiler --- Implementation Task

## Objective

Implement the first production version of the OpenCRO Planning Compiler.

The compiler transforms the declarative planning repository into:

1.  A synchronized Linear workspace.
2.  A single Warp execution manifest (`generated/warp-cycle-<n>.yaml`).

The compiler must **not** execute Warp. It prepares work for Warp.

------------------------------------------------------------------------

# Success Criteria

When complete, the compiler can:

-   Validate the planning repository.
-   Synchronize one selected cycle into Linear.
-   Reconcile issue relationships.
-   Generate one Warp execution manifest.
-   Be rerun safely without creating duplicates.

------------------------------------------------------------------------

# Scope

## In Scope

-   YAML loading
-   Validation
-   DAG construction
-   Markdown rendering
-   Linear GraphQL integration
-   Relationship synchronization
-   Warp manifest generation
-   Tests
-   Documentation

## Out of Scope

-   Warp execution
-   Git branch creation
-   Pull requests
-   Merge automation
-   Reverse synchronization
-   Workflow engine
-   UI

------------------------------------------------------------------------

# Required CLI

``` bash
npm run validate

npm run sync -- --cycle 1 --dry-run

npm run sync -- --cycle 1

npm run render-warp -- --cycle 1
```

------------------------------------------------------------------------

# Implementation Phases

## Phase 1 --- Load

Read:

-   projects.yaml
-   cycles.yaml
-   labels.yaml
-   selected cycle YAML
-   prompt templates

Fail fast on malformed YAML.

------------------------------------------------------------------------

## Phase 2 --- Validate

Validate:

-   required fields
-   unique plan_key
-   references
-   title \<= 80 chars
-   dependency graph
-   parent references
-   labels
-   prompt templates

Abort on validation failure.

------------------------------------------------------------------------

## Phase 3 --- Build DAG

Construct a directed acyclic graph from `depends_on`.

Detect cycles.

Calculate execution waves.

Calculate parallel groups.

------------------------------------------------------------------------

## Phase 4 --- Render

Render concise Linear issue descriptions from task YAML.

Do NOT embed compiled Warp prompts.

Descriptions should include:

-   Plan key
-   Objective
-   Context
-   Inputs
-   Outputs
-   Requirements
-   Acceptance
-   Validation
-   Artifacts
-   Dependencies
-   Execution metadata

------------------------------------------------------------------------

## Phase 5 --- Synchronize Linear

Reuse or create:

-   Projects
-   Cycles
-   Labels

Create or update issues by embedded Plan key.

Never duplicate issues.

------------------------------------------------------------------------

## Phase 6 --- Synchronize Relationships

Query all issues in the selected cycle.

Match issues by embedded Plan key.

Interpret:

``` yaml
depends_on:
  - PF-102
```

as

PF-102 blocks this issue.

Synchronize:

-   create missing relationships
-   remove obsolete relationships
-   preserve existing relationships

Do not infer:

-   related
-   duplicate

Only synchronize:

-   depends_on
-   parent

------------------------------------------------------------------------

## Phase 7 --- Generate Warp Manifest

Generate:

``` text
generated/warp-cycle-1.yaml
```

Include:

-   cycle metadata
-   execution policy
-   waves
-   parallel groups
-   compiled prompts
-   acceptance criteria
-   expected artifacts

Warp must not require Linear identifiers.

------------------------------------------------------------------------

# Canonical Hashing

Normalize each task into canonical JSON:

-   sorted keys
-   insignificant whitespace removed
-   generated fields excluded

Compute SHA-256.

Use only to determine whether a Linear issue must be updated.

------------------------------------------------------------------------

# Error Handling

-   Stop on validation failures.
-   Retry transient GraphQL failures.
-   Never retry authorization failures.
-   Produce actionable diagnostics.
-   Exit non-zero on failure.

------------------------------------------------------------------------

# Reporting

After every run report:

-   created
-   updated
-   unchanged
-   skipped
-   relationship changes
-   validation result

------------------------------------------------------------------------

# Suggested Source Layout

``` text
compiler/
  src/
    cli.ts
    load-plan.ts
    validate.ts
    dag.ts
    render-linear.ts
    render-warp.ts
    sync-linear.ts
    sync-relationships.ts
    graphql/
  tests/
```

------------------------------------------------------------------------

# Tests

Implement automated tests for:

-   parser
-   validation
-   DAG
-   renderer
-   GraphQL client
-   dry run
-   idempotency
-   relationship synchronization
-   Warp manifest generation

Mock Linear.

------------------------------------------------------------------------

# Working Method

1.  Inspect repository.
2.  Confirm schema.
3.  Build validator.
4.  Build DAG.
5.  Render descriptions.
6.  Implement dry run.
7.  Implement synchronization.
8.  Implement relationship reconciliation.
9.  Generate Warp manifest.
10. Add tests.
11. Update README.
12. Deliver completion report.

------------------------------------------------------------------------

# Deliverables

-   Working compiler
-   Automated tests
-   README
-   Generated Warp manifest
-   Successful dry-run
-   Successful synchronization
-   Idempotent second synchronization

Do not redesign the planning repository unless implementation is
impossible. Document any required schema changes before making them.
