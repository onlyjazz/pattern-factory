# Compiler Spec v2

## 1. Purpose

The OpenCRO Planning Compiler converts the declarative planning
repository into two runtime artifacts:

1.  Linear synchronization.
2.  A single Warp execution manifest (`generated/warp-cycle-<n>.yaml`).

The planning YAML is the only source of truth.

## 2. Architectural Principles

-   Git is the system of record.
-   Planning YAML is authoritative.
-   Linear is an operational dashboard.
-   Warp consumes compiled execution artifacts.
-   Synchronization is idempotent.
-   Stable `plan_key` values identify work.

## 3. Repository Structure

``` text
planning/
  projects.yaml
  cycles.yaml
  labels.yaml
  pattern-factory/
  editorial-system/
  experiment-platform/
  gtm-engine/
  prompts/
```

## 4. Outputs

### Linear

Synchronize projects, cycles, labels, issues, parent relationships and
blocking relationships.

### Warp

Generate exactly one execution artifact:

``` text
generated/warp-cycle-1.yaml
```

This is the sole execution artifact for Warp.

## 5. Compiler Pipeline

1.  Load
2.  Validate
3.  Build DAG
4.  Render Linear descriptions
5.  Synchronize Linear
6.  Synchronize relationships
7.  Generate Warp YAML
8.  Report

## 6. Validation

Validate YAML, required fields, unique plan keys, references, title
length, dependency graph, prompt templates and wave ordering.

## 7. Linear Synchronization

-   Reuse projects by exact name.
-   Reuse/create cycles.
-   Reuse/create labels individually.
-   Create or update issues by embedded `Plan key`.

## 8. Synchronize Relationships

Interpret `depends_on` as blocking.

Example:

``` yaml
depends_on:
  - PF-102
  - PF-104
```

Compiler behavior:

-   PF-102 blocks this issue.
-   PF-104 blocks this issue.

Query existing relationships, add missing ones, delete obsolete ones,
leave unchanged relationships untouched. Do not infer `related` or
`duplicate`.

## 9. Idempotency

Repeated synchronization against unchanged YAML must create, update,
delete and duplicate nothing.

Normalize every task to canonical JSON (sorted keys, insignificant
whitespace removed, generated fields excluded) and compute a SHA-256
source hash. Use the hash only to determine whether a Linear issue
requires updating.

## 10. Warp Manifest

Generate `generated/warp-cycle-1.yaml` containing cycle metadata, waves,
parallel groups, compiled prompts and acceptance criteria. Warp must not
depend on Linear identifiers.

## 11. Prompt Compilation

Each Warp prompt is:

    base template
    +
    task template
    +
    task YAML

## 12. Reporting

Report created, updated, unchanged, skipped, deleted relationships and
validation results.

## 13. Non-goals

No Warp execution, Git branching, PR creation, reverse synchronization
or planning redesign.

## 14. Acceptance Criteria

Validation passes, dry-run works, synchronization is idempotent,
relationships match planning, Warp manifest is generated, tests pass and
documentation is complete.
