import { API_BASE } from './config';
export type ID = string

/** Item shape used by the SingleSelect picker. */
export interface SelectItem {
    id: string;
    name: string;
    description?: string;
}
export interface Pattern { id: ID; name: string; description: string; kind: string; story_md?: string | null; story?: string | null; taxonomy?: string | null; }

export interface Threat {
    id: ID;
    name: string;
    description: string;
    tag?: string | null;
    domain?: string | null;
    probability?: number | null;
    damage_description?: string | null;
    spoofing: boolean;
    tampering: boolean;
    repudiation: boolean;
    information_disclosure: boolean;
    denial_of_service: boolean;
    elevation_of_privilege: boolean;
    mitigation_level?: number | null;
    disabled: boolean;
    model_id: number;
    version?: number;
    card_id?: string | null;
    card?: Card | null;
    created_at?: string;
    updated_at?: string;
}

export interface Card {
    id: ID; 
    name: string; 
    description: string; 
    markdown?: string | null; 
    story?: string | null;
    order_index?: number; 
    domain?: string | null; 
    audience?: string | null; 
    maturity?: string | null; 
    pattern_id: number;
    pattern_name?: string | null;
    created_at?: string;
    updated_at?: string;
}

export interface Asset {
    id: ID;
    name: string;
    description: string;
    tag: string | null;
    version: string | null;
    fixed_value: number;
    fixed_value_period: number;
    recurring_value: number;
    include_fixed_value: boolean;
    include_recurring_value: boolean;
    yearly_value: number;
    sle_value?: number | null;
    disabled: boolean;
    model_id: number;
    created_at?: string;
    updated_at?: string;
}

export interface Vulnerability {
    id: ID;
    name: string;
    description: string;
    tag?: string | null;
    version?: number;
    disabled: boolean;
    model_id: number;
    created_at?: string;
    updated_at?: string;
}

export interface Countermeasure {
    id: ID;
    name: string;
    description: string;
    tag?: string | null;
    version?: number;
    yearly_cost: number;
    fixed_implementation_cost: number;
    fixed_cost_period: number;
    recurring_implementation_cost: number;
    include_fixed_cost: boolean;
    include_recurring_cost: boolean;
    implemented: boolean;
    disabled: boolean;
    model_id: number;
    created_at?: string;
    updated_at?: string;
}

export interface Model {
    id: number;
    name: string;
    version?: string | null;
    author?: string | null;
    company?: string | null;
    category?: string | null;
    keywords?: string | null;
    description?: string | null;
    product_id?: number | null;
    intended_use?: string | null;
    org_name?: string | null;
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
        youAreHere?: number;
    };
    created_at?: string;
    updated_at?: string;
}

/** Organization lifecycle status (public.statuses). */
export interface Status {
    id: number;
    name: string;
}

/** Organization (public.orgs) — Product workspace entity. */
export interface Organization {
    id: ID;
    name: string;
    name_before_acquisition?: string | null;
    description?: string | null;
    stage?: string | null;
    funding?: number | null;
    date_funded?: string | null;
    date_founded?: string | null;
    linkedin_company_url?: string | null;
    content_source?: string | null;
    category_id?: number | null;
    content_url?: string | null;
    estimated_annual_sales?: number | null;
    employees?: number | null;
    headquarters?: string | null;
    size?: number | null;
    tier?: number | null;
    status_id?: number | null;
    product_count?: number;
    created_at?: string;
    updated_at?: string;
}

/** FDA-cleared AI-enabled medical device (public.products) — Product workspace entity. */
export interface Product {
    id: ID;
    submission_number: string;
    device: string;
    date_of_final_decision?: string | null;
    intended_use?: string | null;
    indications_for_use?: string | null;
    company?: string | null;
    panel?: string | null;
    primary_product_code?: string | null;
    product_contact_1?: string | null;
    product_contact_2?: string | null;
    product_contact_3?: string | null;
    device_description?: string | null;
    superiority?: string | null;
    competitors?: string | null;
    org_id?: number | null;
    process_flag?: boolean;
    created_at?: string;
    updated_at?: string;
}

/** Person / guest (public.people) — Product workspace entity. */
export interface Person {
    id: ID;
    name: string;
    description?: string | null;
    linkedin_url?: string | null;
    job_description?: string | null;
    content_source?: string | null;
    org_id?: number | null;
    post_id?: number | null;
    content_url?: string | null;
    email?: string | null;
    company_url?: string | null;
    created_at?: string;
    updated_at?: string;
}


export async function getPattern(id: ID) {
    const response = await fetch(`${API_BASE}/patterns/${id}`)
    return await response.json()
}

export async function getPath(id: ID) {
    const response = await fetch(`${API_BASE}/paths/${id}`)
    return await response.json()
}
