import { WarpManifest, Cycle, Task, ExecutionPolicy } from './types.js';
import { DAG } from './dag.js';

export function renderWarpManifest(
  cycle: Cycle,
  executionPolicy: ExecutionPolicy & { name?: string; goal?: string },
  tasks: Task[],
  prompts: Map<string, string>
): WarpManifest {
  const dag = new DAG(tasks);
  const waves = dag.getExecutionWaves();
  const parallelGroups = dag.getParallelGroups();

  // Convert wave indices to wave data
  const waveData = waves.map((taskKeys, index) => ({
    wave: index + 1,
    tasks: taskKeys,
  }));

  // Convert parallel groups to wave data
  const parallelGroupData = Array.from(parallelGroups.entries()).map(([group, taskKeys]) => ({
    group,
    tasks: taskKeys,
  }));

  // Render task summaries
  const taskData = tasks.map(task => {
    const summary: any = {
      plan_key: task.plan_key,
      title: task.title,
      type: task.type,
      objective: task.objective,
      acceptance_criteria: task.acceptance_criteria,
    };

    if (task.artifacts && task.artifacts.length > 0) {
      summary.artifacts = task.artifacts;
    }

    if (task.depends_on && task.depends_on.length > 0) {
      summary.depends_on = task.depends_on;
    }

    // Include compiled Warp prompt if available
    if (task.execution.agent_template) {
      const promptKey = task.execution.agent_template;
      if (prompts.has(promptKey)) {
        summary.warp_prompt = prompts.get(promptKey);
      }
    }

    return summary;
  });

  const manifest: WarpManifest = {
    cycle: cycle.key,
    name: executionPolicy.name || cycle.name,
    goal: executionPolicy.goal || cycle.goal,
    starts_at: cycle.starts_at,
    ends_at: cycle.ends_at,
    execution_policy: {
      start_unblocked_groups_in_parallel: executionPolicy.start_unblocked_groups_in_parallel ?? true,
      stop_on_failed_gate: executionPolicy.stop_on_failed_gate ?? true,
      human_review_at_cycle_gate: executionPolicy.human_review_at_cycle_gate ?? true,
      cycle_gate: executionPolicy.cycle_gate,
    },
    waves: waveData,
    parallel_groups: parallelGroupData,
    tasks: taskData,
  };

  return manifest;
}
