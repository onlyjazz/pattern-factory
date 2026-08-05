import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import { Project, Cycle, Label, Task, ExecutionPolicy } from './types.js';

// Determine planning root - if running from project root, go to planning/; if from planning, stay there
const PLANNING_ROOT = process.cwd().endsWith('/planning') 
  ? process.cwd() 
  : path.join(process.cwd(), 'planning');

interface ProjectsFile {
  projects: Project[];
}

interface CyclesFile {
  cycles: Cycle[];
}

interface LabelsFile {
  labels: Label[];
}

interface TasksFile {
  project: string;
  cycle: string;
  tasks: Task[];
}

interface ExecutionFile {
  cycle: string;
  name: string;
  goal: string;
  timebox_hours: number;
  execution_policy: ExecutionPolicy;
  cycle_gate?: ExecutionPolicy['cycle_gate'];
}

export function loadProjects(): Project[] {
  const filePath = path.join(PLANNING_ROOT, 'projects.yaml');
  const content = fs.readFileSync(filePath, 'utf-8');
  const data = yaml.load(content) as ProjectsFile;
  return data.projects;
}

export function loadCycles(): Cycle[] {
  const filePath = path.join(PLANNING_ROOT, 'cycles.yaml');
  const content = fs.readFileSync(filePath, 'utf-8');
  const data = yaml.load(content) as CyclesFile;
  return data.cycles;
}

export function loadLabels(): Label[] {
  const filePath = path.join(PLANNING_ROOT, 'labels.yaml');
  const content = fs.readFileSync(filePath, 'utf-8');
  const data = yaml.load(content) as LabelsFile;
  return data.labels;
}

export function loadTasksForCycle(cycleKey: string, projects: Project[]): Task[] {
  const tasks: Task[] = [];
  
  for (const project of projects) {
    const filePath = path.join(PLANNING_ROOT, project.key, `${cycleKey}.yaml`);
    
    if (!fs.existsSync(filePath)) {
      console.warn(`Skipping ${filePath}: file not found`);
      continue;
    }
    
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const data = yaml.load(content) as TasksFile;
      
      if (data.tasks && Array.isArray(data.tasks)) {
        tasks.push(...data.tasks);
      }
    } catch (err) {
      console.error(`Error loading ${filePath}:`, err);
      throw err;
    }
  }
  
  return tasks;
}

export function loadExecutionPolicy(cycleKey: string): ExecutionPolicy & { name?: string; goal?: string; timebox_hours?: number } {
  const filePath = path.join(PLANNING_ROOT, 'execution', `${cycleKey}.yaml`);
  
  if (!fs.existsSync(filePath)) {
    console.warn(`Execution policy file not found: ${filePath}`);
    return { start_unblocked_groups_in_parallel: true };
  }
  
  const content = fs.readFileSync(filePath, 'utf-8');
  const data = yaml.load(content) as ExecutionFile;
  
  return {
    start_unblocked_groups_in_parallel: data.execution_policy?.start_unblocked_groups_in_parallel,
    stop_on_failed_gate: data.execution_policy?.stop_on_failed_gate,
    human_review_at_cycle_gate: data.execution_policy?.human_review_at_cycle_gate,
    cycle_gate: data.cycle_gate || data.execution_policy?.cycle_gate,
    name: data.name,
    goal: data.goal,
    timebox_hours: data.timebox_hours,
  };
}

export function loadPromptTemplate(templateName: string): string {
  const filePath = path.join(PLANNING_ROOT, 'prompts', `${templateName}.md`);
  
  if (!fs.existsSync(filePath)) {
    console.warn(`Prompt template not found: ${filePath}`);
    return '';
  }
  
  return fs.readFileSync(filePath, 'utf-8');
}

export function loadAllPrompts(): Map<string, string> {
  const prompts = new Map<string, string>();
  const promptDir = path.join(PLANNING_ROOT, 'prompts');
  
  if (!fs.existsSync(promptDir)) {
    return prompts;
  }
  
  const files = fs.readdirSync(promptDir).filter(f => f.endsWith('.md'));
  
  for (const file of files) {
    const key = path.basename(file, '.md');
    const content = fs.readFileSync(path.join(promptDir, file), 'utf-8');
    prompts.set(key, content);
  }
  
  return prompts;
}
