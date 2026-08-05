import { GraphQLClient, gql } from 'graphql-request';
import { Task, SyncResult } from './types.js';
import { renderLinearDescription, extractLinearMetadata } from './render-linear.js';
import { computeTaskHash, extractPlanKeyFromDescription, extractHashFromDescription } from './hash.js';

export class LinearClient {
  private client: GraphQLClient;
  private projectId: string = '';
  private teamId: string = '';

  constructor(apiKey: string, workspaceSlug: string = 'opencroinc') {
    const endpoint = `https://api.linear.app/graphql`;
    // Linear API expects the key without 'Bearer' prefix
    this.client = new GraphQLClient(endpoint, {
      headers: {
        Authorization: apiKey,
      },
    });
  }

  /**
   * Fetch the first team ID from the workspace.
   * Linear issues must be assigned to a team.
   */
  async ensureTeamId(): Promise<string> {
    if (this.teamId) return this.teamId;

    const query = gql`
      query {
        teams(first: 1) {
          nodes {
            id
            key
            name
          }
        }
      }
    `;

    try {
      const data: any = await this.client.request(query);
      if (data.teams.nodes && data.teams.nodes.length > 0) {
        this.teamId = data.teams.nodes[0].id;
        console.log(`Using team: ${data.teams.nodes[0].name} (${data.teams.nodes[0].key})`);
        return this.teamId;
      }
    } catch (err) {
      console.error('Failed to fetch teams:', err);
    }

    return '';
  }

  /**
   * Find or create the Linear project for this cycle.
   */
  async ensureProject(projectKey: string, projectName: string): Promise<string> {
    const query = gql`
      query {
        projects(first: 100) {
          nodes {
            id
            key
            name
          }
        }
      }
    `;

    try {
      const data: any = await this.client.request(query);
      const project = data.projects.nodes.find((p: any) => p.key === projectKey);
      if (project) {
        this.projectId = project.id;
        return project.id;
      }
    } catch (err) {
      console.error('Failed to fetch projects:', err);
    }

    // For now, assume project exists or use default
    return '';
  }

  /**
   * Query existing issues in a cycle by embedded plan_key.
   */
  async queryIssuesByPlanKeys(planKeys: string[]): Promise<Map<string, any>> {
    const issueMap = new Map<string, any>();

    // Query in batches to avoid hitting GraphQL query size limits
    const batchSize = 10;
    for (let i = 0; i < planKeys.length; i += batchSize) {
      const batch = planKeys.slice(i, i + batchSize);
      try {
        const issues = await this.queryIssuesBatch(batch);
        for (const issue of issues) {
          const planKey = extractPlanKeyFromDescription(issue.description || '');
          if (planKey) {
            issueMap.set(planKey, issue);
          }
        }
      } catch (err) {
        console.error(`Failed to query issues batch ${i / batchSize}:`, err);
      }
    }

    return issueMap;
  }

  private async queryIssuesBatch(planKeys: string[]): Promise<any[]> {
    // Query all issues - Linear API doesn't support powerful search filters
    // We'll filter client-side for issues containing plan keys
    const query = gql`
      query {
        issues(first: 250) {
          nodes {
            id
            title
            description
            state {
              name
            }
          }
        }
      }
    `;

    try {
      const data: any = await this.client.request(query);
      // Filter client-side for issues with Plan Key in description
      const allIssues = data.issues.nodes || [];
      return allIssues.filter((issue: any) => 
        issue.description && issue.description.includes('Plan Key')
      );
    } catch (err) {
      console.error('Failed to query issues:', err);
      return [];
    }
  }

  /**
   * Create a new Linear issue.
   */
  async createIssue(task: Task): Promise<string | null> {
    const metadata = extractLinearMetadata(task);
    const description = renderLinearDescription(task);

    // Ensure we have a teamId before creating
    const teamId = await this.ensureTeamId();
    if (!teamId) {
      console.error(`Failed to create issue ${task.plan_key}: No team available`);
      return null;
    }

    const mutation = gql`
      mutation CreateIssue($input: IssueCreateInput!) {
        issueCreate(input: $input) {
          issue {
            id
            identifier
          }
          success
        }
      }
    `;

    const input = {
      teamId: teamId,
      title: metadata.title,
      description: description,
      priority: this.mapPriorityToLinear(metadata.priority),
      estimate: metadata.estimate,
      labelIds: [], // Label IDs would be populated after ensuring labels exist
    };

    try {
      const data: any = await this.client.request(mutation, { input });
      if (data.issueCreate.success) {
        console.log(`✓ Created issue ${task.plan_key}: ${data.issueCreate.issue.identifier}`);
        return data.issueCreate.issue.id;
      }
    } catch (err) {
      console.error(`Failed to create issue ${task.plan_key}:`, err);
    }

    return null;
  }

  /**
   * Update an existing Linear issue.
   */
  async updateIssue(issueId: string, task: Task): Promise<boolean> {
    const description = renderLinearDescription(task);

    const mutation = gql`
      mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
        issueUpdate(id: $id, input: $input) {
          issue {
            id
          }
          success
        }
      }
    `;

    const metadata = extractLinearMetadata(task);
    const input = {
      title: metadata.title,
      description: description,
      priority: this.mapPriorityToLinear(metadata.priority),
      estimate: metadata.estimate,
    };

    try {
      const data: any = await this.client.request(mutation, { id: issueId, input });
      if (data.issueUpdate.success) {
        console.log(`✓ Updated issue ${task.plan_key}`);
        return true;
      }
    } catch (err) {
      console.error(`Failed to update issue ${task.plan_key}:`, err);
    }

    return false;
  }

  /**
   * Create a "blocks" relationship between issues.
   * issueAId blocks issueBId (issueB depends on issueA)
   */
  async createBlocksRelationship(issueAId: string, issueBId: string): Promise<boolean> {
    const mutation = gql`
      mutation CreateRelation($input: RelationCreateInput!) {
        relationCreate(input: $input) {
          relation {
            id
          }
          success
        }
      }
    `;

    const input = {
      relationshipType: 'blocks',
      fromIssueId: issueAId,
      toIssueId: issueBId,
    };

    try {
      const data: any = await this.client.request(mutation, { input });
      return data.relationCreate.success;
    } catch (err) {
      console.error(`Failed to create blocks relationship:`, err);
      return false;
    }
  }

  /**
   * Delete a relationship between issues.
   */
  async deleteRelationship(relationId: string): Promise<boolean> {
    const mutation = gql`
      mutation DeleteRelation($id: String!) {
        relationDelete(id: $id) {
          success
        }
      }
    `;

    try {
      const data: any = await this.client.request(mutation, { id: relationId });
      return data.relationDelete.success;
    } catch (err) {
      console.error(`Failed to delete relationship:`, err);
      return false;
    }
  }

  private mapPriorityToLinear(priority: string): number {
    // Linear uses 0=No Priority, 1=Urgent, 2=High, 3=Medium, 4=Low
    const map: Record<string, number> = {
      urgent: 1,
      high: 2,
      medium: 3,
      low: 4,
    };
    return map[priority] || 3;
  }
}

/**
 * Perform a dry-run sync: compare current state with target state without mutations.
 */
export async function dryRunSync(
  tasks: Task[],
  existingIssues: Map<string, any>
): Promise<SyncResult> {
  const result: SyncResult = {
    created: [],
    updated: [],
    unchanged: [],
    skipped: [],
    relationshipChanges: {
      created: [],
      updated: [],
      removed: [],
    },
    errors: [],
  };

  for (const task of tasks) {
    const existing = existingIssues.get(task.plan_key);

    if (!existing) {
      result.created.push(task.plan_key);
      continue;
    }

    // Check if task changed
    const newHash = computeTaskHash(task);
    const existingHash = extractHashFromDescription(existing.description || '');

    if (existingHash && existingHash === newHash) {
      result.unchanged.push(task.plan_key);
    } else {
      result.updated.push(task.plan_key);
    }
  }

  return result;
}

/**
 * Execute synchronization: create/update issues in Linear.
 */
export async function executeSync(
  tasks: Task[],
  client: LinearClient,
  existingIssues: Map<string, any>
): Promise<SyncResult> {
  const result: SyncResult = {
    created: [],
    updated: [],
    unchanged: [],
    skipped: [],
    relationshipChanges: {
      created: [],
      updated: [],
      removed: [],
    },
    errors: [],
  };

  for (const task of tasks) {
    const existing = existingIssues.get(task.plan_key);

    if (!existing) {
      // Create new issue
      const issueId = await client.createIssue(task);
      if (issueId) {
        result.created.push(task.plan_key);
      } else {
        result.errors.push(`Failed to create ${task.plan_key}`);
      }
    } else {
      // Check if task changed
      const newHash = computeTaskHash(task);
      const existingHash = extractHashFromDescription(existing.description || '');

      if (existingHash && existingHash === newHash) {
        result.unchanged.push(task.plan_key);
      } else {
        const updated = await client.updateIssue(existing.id, task);
        if (updated) {
          result.updated.push(task.plan_key);
        } else {
          result.errors.push(`Failed to update ${task.plan_key}`);
        }
      }
    }
  }

  return result;
}
