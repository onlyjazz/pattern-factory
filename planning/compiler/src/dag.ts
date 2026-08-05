import { Task } from './types.js';

export class DAG {
  private adjacencyList: Map<string, string[]> = new Map();
  private inDegree: Map<string, number> = new Map();
  private tasks: Map<string, Task>;

  constructor(tasks: Task[]) {
    this.tasks = new Map(tasks.map(t => [t.plan_key, t]));
    this.buildGraph(tasks);
  }

  private buildGraph(tasks: Task[]): void {
    // Initialize adjacency list and in-degree for all tasks
    for (const task of tasks) {
      this.adjacencyList.set(task.plan_key, []);
      this.inDegree.set(task.plan_key, 0);
    }

    // Build edges from depends_on relationships
    for (const task of tasks) {
      if (task.depends_on) {
        for (const dep of task.depends_on) {
          if (this.adjacencyList.has(dep)) {
            this.adjacencyList.get(dep)!.push(task.plan_key);
            this.inDegree.set(task.plan_key, (this.inDegree.get(task.plan_key) || 0) + 1);
          }
        }
      }
    }
  }

  /**
   * Calculate execution waves using topological sort.
   * Each wave is a level of tasks that can run in parallel.
   */
  getExecutionWaves(): string[][] {
    const waves: string[][] = [];
    const inDegreeMap = new Map(this.inDegree);
    const remainingTasks = new Set(this.tasks.keys());

    while (remainingTasks.size > 0) {
      // Find all tasks with in-degree 0
      const currentWave: string[] = [];
      for (const task of remainingTasks) {
        if ((inDegreeMap.get(task) || 0) === 0) {
          currentWave.push(task);
        }
      }

      if (currentWave.length === 0) {
        // This should not happen if DAG is acyclic
        break;
      }

      currentWave.sort();
      waves.push(currentWave);

      // Remove current wave tasks and update in-degrees
      for (const task of currentWave) {
        remainingTasks.delete(task);
        const dependents = this.adjacencyList.get(task) || [];
        for (const dependent of dependents) {
          inDegreeMap.set(dependent, (inDegreeMap.get(dependent) || 1) - 1);
        }
      }
    }

    return waves;
  }

  /**
   * Group tasks by their parallel_group (execution configuration).
   */
  getParallelGroups(): Map<string, string[]> {
    const groups = new Map<string, string[]>();

    for (const task of this.tasks.values()) {
      const group = task.execution?.parallel_group || 'default';
      if (!groups.has(group)) {
        groups.set(group, []);
      }
      groups.get(group)!.push(task.plan_key);
    }

    return groups;
  }

  /**
   * Get all dependencies for a task (transitive closure).
   */
  getDependencies(taskKey: string): Set<string> {
    const deps = new Set<string>();
    const visited = new Set<string>();
    this.collectDependencies(taskKey, deps, visited);
    return deps;
  }

  private collectDependencies(taskKey: string, deps: Set<string>, visited: Set<string>): void {
    if (visited.has(taskKey)) {
      return;
    }
    visited.add(taskKey);

    const task = this.tasks.get(taskKey);
    if (!task || !task.depends_on) {
      return;
    }

    for (const dep of task.depends_on) {
      deps.add(dep);
      this.collectDependencies(dep, deps, visited);
    }
  }

  /**
   * Get all tasks that depend on a given task (transitive closure).
   */
  getDependents(taskKey: string): Set<string> {
    const dependents = new Set<string>();
    const visited = new Set<string>();
    this.collectDependents(taskKey, dependents, visited);
    return dependents;
  }

  private collectDependents(taskKey: string, dependents: Set<string>, visited: Set<string>): void {
    if (visited.has(taskKey)) {
      return;
    }
    visited.add(taskKey);

    const downstreamTasks = this.adjacencyList.get(taskKey) || [];
    for (const downstream of downstreamTasks) {
      dependents.add(downstream);
      this.collectDependents(downstream, dependents, visited);
    }
  }

  /**
   * Check if task A can run in parallel with task B safely.
   */
  canRunInParallel(taskA: string, taskB: string): boolean {
    const depsA = this.getDependencies(taskA);
    const depsB = this.getDependencies(taskB);
    const dependentsA = this.getDependents(taskA);
    const dependentsB = this.getDependents(taskB);

    // A and B can run in parallel if neither depends on the other
    return !depsA.has(taskB) && !depsB.has(taskA) && !dependentsA.has(taskB) && !dependentsB.has(taskA);
  }

  /**
   * Get task by plan_key.
   */
  getTask(taskKey: string): Task | undefined {
    return this.tasks.get(taskKey);
  }

  /**
   * Get all tasks.
   */
  getAllTasks(): Task[] {
    return Array.from(this.tasks.values());
  }
}
