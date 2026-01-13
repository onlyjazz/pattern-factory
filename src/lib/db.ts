export type ID = string
export interface Pattern { id: ID; name: string; description: string; kind: string; story_md?: string | null; taxonomy?: string | null; }

export interface Threat {
    id: ID;
    name: string;
    description: string;
    scenario?: string | null;
    probability?: number | null;
    damage_description?: string | null;
    spoofing: boolean;
    tampering: boolean;
    repudiation: boolean;
    information_disclosure: boolean;
    denial_of_service: boolean;
    elevation_of_privilege: boolean;
    mitigation_level: number;
    disabled: boolean;
    project_id: number;
    cards?: Card[];
    created_at?: string;
    updated_at?: string;
}

export interface Card {
    id: ID; 
    name: string; 
    description: string; 
    markdown?: string | null; 
    order_index?: number; 
    domain?: string | null; 
    audience?: string | null; 
    maturity?: string | null; 
    pattern_id: number;
    created_at?: string;
    updated_at?: string;
}

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
