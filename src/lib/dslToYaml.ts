// lib/utils/dslToYaml.ts
import yaml from 'js-yaml';

export function parseDSLtoYAML(dsl: string): string {
    const workflowMatch = dsl.match(/WORKFLOW\s+"([^"]+)"/);
    const workflowName = workflowMatch ? workflowMatch[1] : 'UnnamedWorkflow';

    const stepRegex = /STEP\s+"([^"]+)"\s*{([^}]+)}/g;
    const steps: any[] = [];

    let match;
    while ((match = stepRegex.exec(dsl)) !== null) {
        const [_, name, body] = match;
        const step: any = { name };

        const action = body.match(/ACTION\s+"([^"]+)"/);
        if (action) step.action = action[1];

        const from = [...body.matchAll(/FROM\s+"([^"]+)"/g)].map(m => m[1]);
        if (from.length) step.from = from;

        const merge = body.match(/MERGE\s+"([^"]+)"/);
        if (merge) step.merge = merge[1];

        const usingMapping = body.match(/USING_MAPPING\s+"([^"]+)"/);
        if (usingMapping) step.using_mapping = usingMapping[1];

        const on = body.match(/ON\s+"([^"]+)"/);
        if (on) step.on = on[1];

        const using = body.match(/USING\s+"([^"]+)"/);
        if (using) step.using = using[1];

        const role = body.match(/ROLE\s+"([^"]+)"/);
        if (role) step.role = role[1];

        const to = body.match(/TO\s+"([^"]+)"/);
        if (to) step.to = to[1];

        const report = body.match(/REPORT\s+"([^"]+)"/);
        if (report) step.report = report[1];

        steps.push(step);
    }

    const flowRegex = /FLOW\s+"([^"]+)"\s*->\s*"([^"]+)"(?:\s*->\s*"([^"]+)")*/g;
    const flows: string[][] = [];

    const flowLines = dsl.match(/FLOW\s+.+/g) || [];
    for (const line of flowLines) {
        const matches = [...line.matchAll(/"([^"]+)"/g)];
        if (matches.length > 1) {
            flows.push(matches.map(m => m[1]));
        }
    }

    const result = {
        workflow: workflowName,
        steps,
        flows,
    };

    return yaml.dump(result, { noRefs: true });
}
