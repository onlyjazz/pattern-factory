# OpenCRO Planning Compiler

The Planning Compiler transforms declarative task definitions spread across project folders into:
1. A synchronized Linear workspace with cross-project dependencies
2. A Warp execution manifest with execution waves and parallel groups

## Installation

The compiler is part of the pattern-factory monorepo. No separate installation needed.

Required npm packages (already installed):
- `graphql-request` — Linear GraphQL API client
- `js-yaml` — YAML parsing
- `dotenv` — Environment variable management

## Configuration

Create a `.env` file in the `planning/` directory:

```bash
# planning/.env
LINEAR_API_KEY=lin_api_xxxxx
```

Get your Linear API key from: https://linear.app/settings/account/api

## Commands

### Validate All Cycles

```bash
npm run validate
```

Checks all project cycles for:
- Required fields (plan_key, title, type, project, cycle, priority, estimate, execution, objective, acceptance_criteria)
- Duplicate plan_keys
- Invalid references (projects, cycles, labels, dependencies)
- Title length ≤ 80 characters
- Circular dependencies
- Schema compliance

Output: List of validation errors grouped by cycle. Exit code 0 on success, 1 on failure.

### Synchronize to Linear (Dry-Run)

```bash
npm run sync -- --cycle cycle-1 --dry-run
```

Shows what would be created/updated in Linear without making changes:
- Queries existing Linear issues for plan_keys
- Detects new tasks (would create issues)
- Detects changed tasks (would update issues)
- Reports task dependencies and relationships

Output: Sync report with created/updated/unchanged/error counts.

### Synchronize to Linear (Execute)

```bash
npm run sync -- --cycle cycle-1
```

**WARNING**: This creates and updates Linear issues. Cannot be undone directly.

Creates new Linear issues for each task and updates existing issues if the task definition changed (detected via content hash).

Idempotent: Running twice produces no changes on second run (same hash = no update).

Output: Sync report with creation/update counts and any errors.

### Generate Warp Manifest

```bash
npm run render-warp -- --cycle cycle-1
```

Generates `/Users/dl/code/pattern-factory/generated/warp-cycle-1.yaml` containing:
- Execution waves (task groups that can run in parallel)
- Parallel groups (tasks grouped by execution metadata)
- Task summaries with acceptance criteria
- Compiled Warp prompts for agent-template tasks
- Execution policy and cycle gate configuration

Output: Manifest file with cycle metadata, execution policy, and task details.

## Architecture

### Data Flow

```
projects.yaml ──────┐
cycles.yaml ────────┤
labels.yaml ────────┤
planning/*/cycle-N.yaml ──┤
execution/cycle-N.yaml ───├──> Load ──> Validate ──> DAG ──> Render ──> Sync
prompts/*.md ──────────────┘
```

### Modules

- **load.ts** — Load YAML files from planning repository
- **validate.ts** — Schema validation and dependency checking
- **dag.ts** — Directed acyclic graph for task ordering
- **hash.ts** — Canonical hashing for change detection
- **render-linear.ts** — Convert tasks to Linear issue markdown
- **render-warp.ts** — Generate Warp execution manifest YAML
- **sync-linear.ts** — Linear GraphQL client and issue synchronization
- **cli.ts** — Command-line interface entry point

### Key Concepts

**Plan Key** — Stable external identifier (e.g., PF-101) never replaced by Linear issue ID. Used as the canonical identity across systems.

**Canonical Hash** — SHA-256 hash of normalized task YAML (sorted keys, no insignificant whitespace). Used to detect task changes for idempotent updates.

**Execution Wave** — Set of tasks with no inter-dependencies that can run in parallel. Computed via topological sort of the dependency graph.

**Parallel Group** — Tasks grouped by their `execution.parallel_group` field. Separate from waves; used for execution organization.

## Example: Synchronize Cycle 1

1. **Validate first:**
   ```bash
   npm run validate
   ```
   Check for errors specific to cycle-1:
   ```bash
   npm run validate 2>&1 | grep -A 5 "cycle-1"
   ```

2. **Dry-run sync:**
   ```bash
   npm run sync -- --cycle cycle-1 --dry-run
   ```
   Review output. Confirm created issues match expected tasks.

3. **Execute sync:**
   ```bash
   npm run sync -- --cycle cycle-1
   ```
   Issues are created in Linear.

4. **Generate Warp manifest:**
   ```bash
   npm run render-warp -- --cycle cycle-1
   ```
   Manifest saved to `generated/warp-cycle-1.yaml`.

5. **Verify idempotency:**
   ```bash
   npm run sync -- --cycle cycle-1 --dry-run
   ```
   Should report "Unchanged: 14" with no created/updated.

## Task YAML Structure

```yaml
project: pattern-factory
cycle: cycle-1
tasks:
  - plan_key: PF-101
    title: Task Title (≤80 chars)
    type: inspect|design|implement|integrate|generate|validate|deploy|review|human|analyze|operate
    project: pattern-factory
    cycle: cycle-1
    priority: urgent|high|normal|low
    estimate: 5  # Story points
    labels: [agent-ready, ai, data]  # Optional
    execution:
      executor: warp-agent|human
      agent_template: inspect|engineering|validate|operate|human  # Optional
      parallel_group: c1-schema  # Optional
      reviewer: Danny  # Optional
      review_required: none|sample|full
    objective: What does this task accomplish?
    context: Why is this important? (optional)
    inputs: [Input A, Input B]  # Optional
    outputs: [Output A, Output B]  # Optional
    requirements: [Requirement A]  # Optional
    validation: [Test 1, Test 2]  # Optional
    artifacts: [Artifact A]  # Optional
    acceptance_criteria:
      - Criterion A
      - Criterion B
    depends_on: [PF-100, PF-102]  # Optional
    run_with: [PF-108]  # Optional (can run in parallel)
    constraints: [Constraint A]  # Optional
    warp:  # Optional
      completion_report: [Instruction 1, Instruction 2]
```

## Linear Issue Format

Each Linear issue contains:

- **Title** — Task title (from task.title)
- **Description** — Markdown with task metadata:
  - Plan Key (embedded, stable identifier)
  - Objective, context, inputs, outputs, requirements
  - Acceptance criteria, validation, artifacts, constraints
  - Task metadata (type, priority, executor, reviewer)
  - Task dependencies
  - Content hash (hidden, used for change detection)
- **Priority** — Mapped from task priority: urgent→urgent, high→high, normal→medium, low→low
- **Estimate** — Story points from task.estimate
- **Labels** — From task.labels
- **Relationships** — depends_on mapped to "blocks" relationship

## Testing

No formal test suite yet. Manual testing via:

1. `npm run validate` — Validates all cycles
2. `npm run render-warp -- --cycle cycle-1` — Generates manifest
3. `npm run sync -- --cycle cycle-1 --dry-run` — Preview sync without changes

## Error Handling

- **Validation errors** — Exit code 1, detailed error list by cycle
- **Missing files** — Warned and skipped, cycle continues
- **Linear API errors** — Retries not implemented; 400/401/403 errors are fatal
- **GraphQL errors** — Printed to stderr, sync continues with empty issue list (dry-run only)

## Limitations & Future Work

1. **No Linear reverse-sync** — Changes to Linear issues are not pulled back into YAML
2. **Limited GraphQL filtering** — Queries fetch all issues, filters applied client-side
3. **No relationship cleanup** — Old dependencies not removed if task.depends_on is cleared
4. **Single API key** — No per-project Linear workspace support
5. **No cycle-to-cycle relationship mapping** — Cross-cycle depends_on treated as invalid

## Troubleshooting

### "LINEAR_API_KEY not set in .env"

Ensure `.env` exists in `planning/` directory with valid API key:
```bash
cat planning/.env | grep LINEAR_API_KEY
```

### "Dependency not found: PF-100"

Task references a plan_key that doesn't exist in the same cycle. Check:
- Cross-cycle dependencies (not supported within single cycle validation)
- Typo in plan_key
- Task not yet defined

### "GraphQL error: Field not defined"

Linear API query syntax error. Usually indicates outdated GraphQL schema. Check:
- Linear API changelog: https://linear.app/changelog
- graphql-request version compatibility

### "Validation passed but issues not created"

Check dry-run output:
```bash
npm run sync -- --cycle cycle-1 --dry-run
```

If dry-run shows "Created: 0", tasks failed validation (hidden errors). Re-run validate to see details.

## File Locations

- Source: `planning/compiler/src/*.ts`
- Tests: `planning/compiler/tests/*.test.ts` (not yet implemented)
- Output: `planning/generated/warp-cycle-N.yaml`
- Config: `planning/.env`

## Contact

For issues or questions about the compiler, refer to the planning architecture docs:
- `planning/architecture/ARCHITECTURE.md`
- `planning/architecture/compiler-spec-v2.md`
- `planning/architecture/compiler-implementation-task.md`
