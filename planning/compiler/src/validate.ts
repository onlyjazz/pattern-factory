import { Task, Cycle, Label, ValidationError } from './types.js';

export class Validator {
  private labels: Map<string, Label>;
  private cycles: Map<string, Cycle>;
  private projectKeys: Set<string>;
  private errors: ValidationError[] = [];

  constructor(labels: Label[], cycles: Cycle[], projectKeys: Set<string>) {
    this.labels = new Map(labels.map(l => [l.key, l]));
    this.cycles = new Map(cycles.map(c => [c.key, c]));
    this.projectKeys = projectKeys;
  }

  validate(tasks: Task[]): ValidationError[] {
    this.errors = [];

    // Check for duplicate plan_keys
    const planKeySet = new Set<string>();
    for (const task of tasks) {
      if (planKeySet.has(task.plan_key)) {
        this.errors.push({
          code: 'DUPLICATE_PLAN_KEY',
          message: `Duplicate plan_key: ${task.plan_key}`,
          task_key: task.plan_key,
        });
      }
      planKeySet.add(task.plan_key);
    }

    // Validate each task
    for (const task of tasks) {
      this.validateTask(task, tasks);
    }

    // Check dependency graph for cycles
    this.validateDependencyGraph(tasks);

    return this.errors;
  }

  private validateTask(task: Task, allTasks: Task[]): void {
    // Required fields
    const requiredFields = [
      'plan_key',
      'title',
      'type',
      'project',
      'cycle',
      'priority',
      'estimate',
      'execution',
      'objective',
      'acceptance_criteria',
    ];

    for (const field of requiredFields) {
      if (!task[field as keyof Task]) {
        this.errors.push({
          code: 'MISSING_REQUIRED_FIELD',
          message: `Missing required field: ${field}`,
          task_key: task.plan_key,
          field,
        });
      }
    }

    // Title length
    if (task.title && task.title.length > 80) {
      this.errors.push({
        code: 'TITLE_TOO_LONG',
        message: `Title exceeds 80 characters: ${task.title.length}`,
        task_key: task.plan_key,
        field: 'title',
      });
    }

    // Valid project
    if (task.project && !this.projectKeys.has(task.project)) {
      this.errors.push({
        code: 'INVALID_PROJECT',
        message: `Project not defined: ${task.project}`,
        task_key: task.plan_key,
        field: 'project',
      });
    }

    // Valid cycle
    if (task.cycle && !this.cycles.has(task.cycle)) {
      this.errors.push({
        code: 'INVALID_CYCLE',
        message: `Cycle not defined: ${task.cycle}`,
        task_key: task.plan_key,
        field: 'cycle',
      });
    }

    // Valid type
    const validTypes = ['inspect', 'design', 'implement', 'integrate', 'generate', 'validate', 'deploy', 'review', 'human', 'analyze', 'operate'];
    if (task.type && !validTypes.includes(task.type)) {
      this.errors.push({
        code: 'INVALID_TYPE',
        message: `Invalid task type: ${task.type}`,
        task_key: task.plan_key,
        field: 'type',
      });
    }

    // Valid priority
    const validPriorities = ['urgent', 'high', 'normal', 'low'];
    if (task.priority && !validPriorities.includes(task.priority)) {
      this.errors.push({
        code: 'INVALID_PRIORITY',
        message: `Invalid priority: ${task.priority}`,
        task_key: task.plan_key,
        field: 'priority',
      });
    }

    // Execution config
    if (task.execution) {
      const validExecutors = ['warp-agent', 'human'];
      if (task.execution.executor && !validExecutors.includes(task.execution.executor)) {
        this.errors.push({
          code: 'INVALID_EXECUTOR',
          message: `Invalid executor: ${task.execution.executor}`,
          task_key: task.plan_key,
          field: 'execution.executor',
        });
      }

      const validReviewRequired = ['none', 'sample', 'full'];
      if (task.execution.review_required && !validReviewRequired.includes(task.execution.review_required)) {
        this.errors.push({
          code: 'INVALID_REVIEW_REQUIRED',
          message: `Invalid review_required: ${task.execution.review_required}`,
          task_key: task.plan_key,
          field: 'execution.review_required',
        });
      }
    }

    // Valid labels
    if (task.labels) {
      for (const label of task.labels) {
        if (!this.labels.has(label)) {
          this.errors.push({
            code: 'INVALID_LABEL',
            message: `Label not defined: ${label}`,
            task_key: task.plan_key,
            field: 'labels',
          });
        }
      }
    }

    // Validate depends_on references
    if (task.depends_on) {
      const allPlanKeys = new Set(allTasks.map(t => t.plan_key));
      for (const depKey of task.depends_on) {
        if (!allPlanKeys.has(depKey)) {
          this.errors.push({
            code: 'INVALID_DEPENDENCY',
            message: `Dependency not found: ${depKey}`,
            task_key: task.plan_key,
            field: 'depends_on',
          });
        }
      }
    }

    // Validate run_with references
    if (task.run_with) {
      const allPlanKeys = new Set(allTasks.map(t => t.plan_key));
      for (const runWithKey of task.run_with) {
        if (!allPlanKeys.has(runWithKey)) {
          this.errors.push({
            code: 'INVALID_RUN_WITH',
            message: `run_with task not found: ${runWithKey}`,
            task_key: task.plan_key,
            field: 'run_with',
          });
        }
      }
    }

    // Acceptance criteria must be non-empty
    if (!task.acceptance_criteria || task.acceptance_criteria.length === 0) {
      this.errors.push({
        code: 'EMPTY_ACCEPTANCE_CRITERIA',
        message: 'Task must have at least one acceptance criterion',
        task_key: task.plan_key,
        field: 'acceptance_criteria',
      });
    }
  }

  private validateDependencyGraph(tasks: Task[]): void {
    const taskMap = new Map(tasks.map(t => [t.plan_key, t]));
    const visited = new Set<string>();
    const recursionStack = new Set<string>();

    for (const task of tasks) {
      if (!visited.has(task.plan_key)) {
        this.detectCycle(task.plan_key, taskMap, visited, recursionStack);
      }
    }
  }

  private detectCycle(
    taskKey: string,
    taskMap: Map<string, Task>,
    visited: Set<string>,
    recursionStack: Set<string>
  ): void {
    visited.add(taskKey);
    recursionStack.add(taskKey);

    const task = taskMap.get(taskKey);
    if (!task || !task.depends_on) {
      recursionStack.delete(taskKey);
      return;
    }

    for (const dep of task.depends_on) {
      if (!visited.has(dep)) {
        this.detectCycle(dep, taskMap, visited, recursionStack);
      } else if (recursionStack.has(dep)) {
        this.errors.push({
          code: 'CIRCULAR_DEPENDENCY',
          message: `Circular dependency detected involving: ${taskKey} -> ${dep}`,
          task_key: taskKey,
          field: 'depends_on',
        });
      }
    }

    recursionStack.delete(taskKey);
  }
}
