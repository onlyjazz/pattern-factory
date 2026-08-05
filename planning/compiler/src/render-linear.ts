import { Task } from './types.js';
import { computeTaskHash, embedHashInDescription } from './hash.js';

/**
 * Render a task as a Linear issue description in markdown.
 * Includes all necessary fields for context and execution.
 */
export function renderLinearDescription(task: Task): string {
  const lines: string[] = [];

  // Plan Key (used as stable identifier)
  lines.push(`**Plan Key:** ${task.plan_key}`);
  lines.push('');

  // Objective
  lines.push('## Objective');
  lines.push(task.objective);
  lines.push('');

  // Context
  if (task.context) {
    lines.push('## Context');
    lines.push(task.context);
    lines.push('');
  }

  // Inputs
  if (task.inputs && task.inputs.length > 0) {
    lines.push('## Inputs');
    for (const input of task.inputs) {
      lines.push(`- ${input}`);
    }
    lines.push('');
  }

  // Outputs
  if (task.outputs && task.outputs.length > 0) {
    lines.push('## Outputs');
    for (const output of task.outputs) {
      lines.push(`- ${output}`);
    }
    lines.push('');
  }

  // Requirements
  if (task.requirements && task.requirements.length > 0) {
    lines.push('## Requirements');
    for (const req of task.requirements) {
      lines.push(`- ${req}`);
    }
    lines.push('');
  }

  // Acceptance Criteria
  lines.push('## Acceptance Criteria');
  for (const criterion of task.acceptance_criteria) {
    lines.push(`- ${criterion}`);
  }
  lines.push('');

  // Validation
  if (task.validation && task.validation.length > 0) {
    lines.push('## Validation');
    for (const val of task.validation) {
      lines.push(`- ${val}`);
    }
    lines.push('');
  }

  // Artifacts
  if (task.artifacts && task.artifacts.length > 0) {
    lines.push('## Artifacts');
    for (const artifact of task.artifacts) {
      lines.push(`- ${artifact}`);
    }
    lines.push('');
  }

  // Constraints
  if (task.constraints && task.constraints.length > 0) {
    lines.push('## Constraints');
    for (const constraint of task.constraints) {
      lines.push(`- ${constraint}`);
    }
    lines.push('');
  }

  // Dependencies
  if (task.depends_on && task.depends_on.length > 0) {
    lines.push('## Depends On');
    for (const dep of task.depends_on) {
      lines.push(`- ${dep}`);
    }
    lines.push('');
  }

  // Task metadata
  lines.push('---');
  lines.push('## Task Metadata');
  lines.push(`**Type:** ${task.type}`);
  lines.push(`**Priority:** ${task.priority}`);
  lines.push(`**Estimate:** ${task.estimate} points`);
  lines.push(`**Executor:** ${task.execution.executor}`);
  if (task.execution.agent_template) {
    lines.push(`**Agent Template:** ${task.execution.agent_template}`);
  }
  if (task.execution.parallel_group) {
    lines.push(`**Parallel Group:** ${task.execution.parallel_group}`);
  }
  if (task.execution.reviewer) {
    lines.push(`**Reviewer:** ${task.execution.reviewer}`);
  }
  lines.push(`**Review Required:** ${task.execution.review_required}`);

  let description = lines.join('\n');

  // Embed hash as hidden comment for change detection
  const hash = computeTaskHash(task);
  description = embedHashInDescription(description, hash);

  return description;
}

/**
 * Extract metadata for Linear issue creation/update.
 */
export interface LinearIssueMetadata {
  title: string;
  description: string;
  priority: 'urgent' | 'high' | 'medium' | 'low';
  estimate: number;
  labels: string[];
  planKey: string;
}

export function extractLinearMetadata(task: Task): LinearIssueMetadata {
  // Map task priority to Linear priority
  const priorityMap: Record<string, 'urgent' | 'high' | 'medium' | 'low'> = {
    urgent: 'urgent',
    high: 'high',
    normal: 'medium',
    low: 'low',
  };

  return {
    title: task.title,
    description: renderLinearDescription(task),
    priority: priorityMap[task.priority] || 'medium',
    estimate: task.estimate,
    labels: task.labels || [],
    planKey: task.plan_key,
  };
}
