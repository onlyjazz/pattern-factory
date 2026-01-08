export type ID = string
export interface Pattern { id: ID; name: string; description: string; kind: string; }

export interface PathNode {
    id: string;
    type: string; // assumption, decision, state
    label: string;
    serial?: number;
    optionality?: {
        collapses: boolean;
        reason: string;
        irreversible: boolean;
    };
}

export interface PathEdge {
    from_node: string;
    to_node: string;
    reason: string;
}

export interface Path {
    id: ID;
    name: string;
    description?: string;
    yaml?: {
        nodes: PathNode[];
        edges: PathEdge[];
    };
    created_at?: string;
    updated_at?: string;
}

const apiBase = "http://localhost:8000"

export async function getPattern(id: ID) {
    const response = await fetch(`${apiBase}/patterns/${id}`)
    return await response.json()
}

export async function getPath(id: ID) {
    const response = await fetch(`${apiBase}/paths/${id}`)
    return await response.json()
}
