/**
 * Compiler type definitions
 */

export interface Project {
  key: string;
  name: string;
  summary: string;
  description: string;
}

export interface Cycle {
  number: number;
  key: string;
  name: string;
  starts_at: string;
  ends_at: string;
  goal: string;
}

export interface Label {
  key: string;
  name: string;
  color: string;
  description: string;
}

export interface ExecutionConfig {
  executor: 'warp-agent' | 'human';
  agent_template?: string;
  parallel_group?: string;
  reviewer?: string;
  review_required: 'none' | 'sample' | 'full';
}

export interface Task {
  plan_key: string;
  title: string;
  type: 'inspect' | 'design' | 'implement' | 'integrate' | 'generate' | 'validate' | 'deploy' | 'review' | 'human' | 'analyze' | 'operate';
  project: string;
  cycle: string;
  priority: 'urgent' | 'high' | 'normal' | 'low';
  estimate: number;
  execution: ExecutionConfig;
  objective: string;
  acceptance_criteria: string[];
  
  // Optional fields
  depends_on?: string[];
  run_with?: string[];
  labels?: string[];
  context?: string;
  inputs?: string[];
  outputs?: string[];
  requirements?: string[];
  validation?: string[];
  artifacts?: string[];
  constraints?: string[];
  warp?: {
    completion_report?: string[];
  };
}

export interface CompiledCycle {
  cycle: Cycle;
  executionPolicy: ExecutionPolicy;
  tasks: Task[];
  tasksByKey: Map<string, Task>;
  dagLevels: string[][];
  parallelGroups: Map<string, string[]>;
}

export interface ExecutionPolicy {
  start_unblocked_groups_in_parallel?: boolean;
  stop_on_failed_gate?: boolean;
  human_review_at_cycle_gate?: boolean;
  cycle_gate?: {
    reviewer?: string;
    criteria?: string[];
  };
}

export interface ValidationError {
  code: string;
  message: string;
  task_key?: string;
  field?: string;
}

export interface SyncResult {
  created: string[];
  updated: string[];
  unchanged: string[];
  skipped: string[];
  relationshipChanges: {
    created: string[];
    updated: string[];
    removed: string[];
  };
  errors: string[];
}

export interface WarpManifest {
  cycle: string;
  name: string;
  goal: string;
  starts_at: string;
  ends_at: string;
  execution_policy: ExecutionPolicy;
  waves: {
    wave: number;
    tasks: string[];
  }[];
  parallel_groups: {
    group: string;
    tasks: string[];
  }[];
  tasks: {
    plan_key: string;
    title: string;
    type: string;
    objective: string;
    acceptance_criteria: string[];
    artifacts?: string[];
    depends_on?: string[];
    warp_prompt?: string;
  }[];
}

export interface LinearIssue {
  id: string;
  title: string;
  description: string;
  state: string;
  cycle?: { name: string };
  labels?: { nodes: Array<{ name: string }> };
  relations?: Array<{ relatedIssue: LinearIssue }>;
}
