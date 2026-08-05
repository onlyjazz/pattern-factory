import crypto from 'crypto';
import { Task } from './types.js';

/**
 * Compute canonical hash of a task for change detection.
 * Excludes generated fields and normalizes whitespace.
 */
export function computeTaskHash(task: Task): string {
  // Create a canonical representation excluding generated/meta fields
  const canonical = {
    plan_key: task.plan_key,
    title: task.title,
    type: task.type,
    project: task.project,
    cycle: task.cycle,
    priority: task.priority,
    estimate: task.estimate,
    execution: task.execution ? normalizeExecution(task.execution) : undefined,
    objective: task.objective,
    acceptance_criteria: task.acceptance_criteria,
    depends_on: task.depends_on ? task.depends_on.sort() : undefined,
    run_with: task.run_with ? task.run_with.sort() : undefined,
    labels: task.labels ? task.labels.sort() : undefined,
    context: task.context,
    inputs: task.inputs,
    outputs: task.outputs,
    requirements: task.requirements,
    validation: task.validation,
    artifacts: task.artifacts,
    constraints: task.constraints,
  };

  // Convert to JSON with sorted keys and no extra whitespace
  const json = JSON.stringify(canonical, Object.keys(canonical).sort());
  
  // Compute SHA-256 hash
  return crypto.createHash('sha256').update(json).digest('hex');
}

function normalizeExecution(execution: Task['execution']) {
  return {
    executor: execution.executor,
    agent_template: execution.agent_template,
    parallel_group: execution.parallel_group,
    reviewer: execution.reviewer,
    review_required: execution.review_required,
  };
}

/**
 * Extract plan_key from Linear issue description.
 * Format: "**Plan Key:** PF-101"
 */
export function extractPlanKeyFromDescription(description: string): string | null {
  const match = description.match(/\*\*Plan Key:\*\*\s+(\S+)/);
  return match ? match[1] : null;
}

/**
 * Extract hash from Linear issue description (stored as comment or hidden field).
 * For now, we'll compute it client-side and compare with computed hash.
 */
export function extractHashFromDescription(description: string): string | null {
  // Look for a hidden hash comment in format: <!-- hash: ABC123... -->
  const match = description.match(/<!--\s*hash:\s*([a-f0-9]{64})\s*-->/);
  return match ? match[1] : null;
}

/**
 * Embed hash in issue description as hidden HTML comment.
 */
export function embedHashInDescription(description: string, hash: string): string {
  // Remove existing hash if present
  const cleaned = description.replace(/<!--\s*hash:\s*[a-f0-9]{64}\s*-->\n?/g, '');
  return `<!-- hash: ${hash} -->\n${cleaned}`;
}
