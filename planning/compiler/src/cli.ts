#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import yaml from 'js-yaml';
import dotenv from 'dotenv';
import { loadProjects, loadCycles, loadLabels, loadTasksForCycle, loadExecutionPolicy, loadAllPrompts } from './load.js';
import { Validator } from './validate.js';
import { DAG } from './dag.js';
import { renderWarpManifest } from './render-warp.js';
import { LinearClient, dryRunSync, executeSync } from './sync-linear.js';

// Load environment variables - check planning directory and root
const planningRoot = process.cwd().endsWith('/planning') 
  ? process.cwd() 
  : path.join(process.cwd(), 'planning');
dotenv.config({ path: path.join(planningRoot, '.env') });
dotenv.config({ path: path.resolve(process.cwd(), '.env') }); // Also check root

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  try {
    switch (command) {
      case 'validate':
        await handleValidate();
        break;
      case 'sync':
        await handleSync(args);
        break;
      case 'render-warp':
        await handleRenderWarp(args);
        break;
      default:
        console.error(`Unknown command: ${command}`);
        console.error('Usage: compiler [validate|sync|render-warp] [options]');
        process.exit(1);
    }
  } catch (err) {
    console.error('Error:', err);
    process.exit(1);
  }
}

async function handleValidate() {
  console.log('Validating planning repository...\n');

  const projects = loadProjects();
  const cycles = loadCycles();
  const labels = loadLabels();

  const projectKeys = new Set(projects.map(p => p.key));
  const validator = new Validator(labels, cycles, projectKeys);

  let totalErrors = 0;

  // Validate all cycles
  for (const cycle of cycles) {
    console.log(`Validating ${cycle.key}...`);
    const tasks = loadTasksForCycle(cycle.key, projects);
    const errors = validator.validate(tasks);

    if (errors.length === 0) {
      console.log(`  ✓ ${tasks.length} tasks, no errors\n`);
    } else {
      console.log(`  ✗ Found ${errors.length} validation errors:\n`);
      for (const err of errors) {
        console.log(`    - [${err.code}] ${err.task_key || ''}: ${err.message}`);
      }
      console.log('');
      totalErrors += errors.length;
    }
  }

  if (totalErrors === 0) {
    console.log('✓ Validation passed for all cycles!\n');
    process.exit(0);
  } else {
    console.log(`✗ Validation failed with ${totalErrors} errors.\n`);
    process.exit(1);
  }
}

async function handleSync(args: string[]) {
  const cycleArg = args.find(a => a.startsWith('--cycle'))?.split('=')[1] || args[args.indexOf('--cycle') + 1];
  const isDryRun = args.includes('--dry-run');

  if (!cycleArg) {
    console.error('Usage: compiler sync --cycle <cycle-key> [--dry-run]');
    console.error('Example: compiler sync --cycle cycle-1 --dry-run');
    process.exit(1);
  }

  console.log(`Synchronizing ${cycleArg}${isDryRun ? ' (DRY RUN)' : ''}...\n`);

  const projects = loadProjects();
  const cycles = loadCycles();
  const tasks = loadTasksForCycle(cycleArg, projects);

  if (tasks.length === 0) {
    console.log(`No tasks found for ${cycleArg}`);
    process.exit(0);
  }

  const apiKey = process.env.LINEAR_API_KEY;
  if (!apiKey) {
    console.error('LINEAR_API_KEY not set in .env');
    process.exit(1);
  }

  const client = new LinearClient(apiKey);
  const planKeys = tasks.map(t => t.plan_key);
  const existingIssues = await client.queryIssuesByPlanKeys(planKeys);

  console.log(`Found ${existingIssues.size} existing issues in Linear\n`);

  if (isDryRun) {
    const result = await dryRunSync(tasks, existingIssues);
    reportSync(result);
    process.exit(0);
  } else {
    const result = await executeSync(tasks, client, existingIssues);
    reportSync(result);
    process.exit(result.errors.length === 0 ? 0 : 1);
  }
}

async function handleRenderWarp(args: string[]) {
  const cycleArg = args.find(a => a.startsWith('--cycle'))?.split('=')[1] || args[args.indexOf('--cycle') + 1];

  if (!cycleArg) {
    console.error('Usage: compiler render-warp --cycle <cycle-key>');
    console.error('Example: compiler render-warp --cycle cycle-1');
    process.exit(1);
  }

  console.log(`Rendering Warp manifest for ${cycleArg}...\n`);

  const projects = loadProjects();
  const cycles = loadCycles();
  const tasks = loadTasksForCycle(cycleArg, projects);
  const executionPolicy = loadExecutionPolicy(cycleArg);
  const prompts = loadAllPrompts();

  if (tasks.length === 0) {
    console.log(`No tasks found for ${cycleArg}`);
    process.exit(0);
  }

  const cycle = cycles.find(c => c.key === cycleArg);
  if (!cycle) {
    console.error(`Cycle not found: ${cycleArg}`);
    process.exit(1);
  }

  const manifest = renderWarpManifest(cycle, executionPolicy, tasks, prompts);

  // Ensure output directory
  const outputDir = path.resolve(process.cwd(), 'generated');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const outputPath = path.join(outputDir, `warp-${cycleArg}.yaml`);
  fs.writeFileSync(outputPath, yaml.dump(manifest, { lineWidth: -1 }), 'utf-8');

  console.log(`✓ Generated ${outputPath}`);
  console.log(`  - ${tasks.length} tasks`);
  console.log(`  - ${manifest.waves.length} execution waves`);
  console.log(`  - ${manifest.parallel_groups.length} parallel groups\n`);

  process.exit(0);
}

function reportSync(result: any) {
  console.log('=== Sync Report ===\n');

  if (result.created.length > 0) {
    console.log(`Created: ${result.created.length}`);
    for (const key of result.created) {
      console.log(`  - ${key}`);
    }
    console.log('');
  }

  if (result.updated.length > 0) {
    console.log(`Updated: ${result.updated.length}`);
    for (const key of result.updated) {
      console.log(`  - ${key}`);
    }
    console.log('');
  }

  if (result.unchanged.length > 0) {
    console.log(`Unchanged: ${result.unchanged.length}`);
  }

  if (result.skipped.length > 0) {
    console.log(`Skipped: ${result.skipped.length}`);
  }

  if (result.errors.length > 0) {
    console.log(`\nErrors: ${result.errors.length}`);
    for (const err of result.errors) {
      console.log(`  - ${err}`);
    }
  }

  console.log('');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
