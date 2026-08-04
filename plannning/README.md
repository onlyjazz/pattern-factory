# OpenCRO Planning Repository v2

Git is the source of truth. Linear is the control plane. Warp is the execution engine.

## Contents

- 4 project folders
- 6 one-week cycles represented as 24-hour execution DAGs
- 76 granular tasks
- reusable agent templates
- stable plan keys and explicit dependencies
- project/cycle execution manifests

## Layout

```
planning/
  projects.yaml
  cycles.yaml
  labels.yaml
  prompts/
  schema/
  execution/
  pattern-factory/
  editorial-system/
  experiment-platform/
  gtm-engine/
  importer/
```

## Validate

```bash
python planning/importer/validate.py
```

## Render a Warp prompt

```bash
python planning/importer/render_prompt.py PF-101
```

## Execution model

Each cycle manifest is a DAG organized into waves and parallel groups. Launch all unblocked groups in a wave concurrently. Move to the next wave only when the current gate passes or Danny explicitly accepts a blocker.

The YAML intentionally avoids Linear IDs. `plan_key` is permanent. A future sync tool should create Linear objects first, record the Linear ID mapping, and wire relationships in a second pass.
