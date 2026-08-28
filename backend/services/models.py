"""
services/models.py
Pydantic request models for the Pattern Factory API.

All Create/Update request bodies used by the FastAPI endpoints in
services/api.py are defined here to keep api.py focused on routing
and database logic. When adding or altering database tables, update
the corresponding models in this file (see backend/db/AGENTS.md).
"""

from typing import Optional

from pydantic import BaseModel


# -------------------------------------------------------------------------
# Organizations
# -------------------------------------------------------------------------
class OrgCreate(BaseModel):
    """Create a new organization."""
    name: str
    description: str | None = None
    stage: str | None = None
    funding: float | None = None
    date_funded: str | None = None
    date_founded: str | None = None
    linkedin_company_url: str | None = None
    content_source: str | None = None
    category_id: int | None = None
    content_url: str | None = None
    estimated_annual_sales: float | None = None
    employees: int | None = None
    headquarters: str | None = None
    size: int | None = None
    tier: int | None = None
    study_arm: str | None = None
    randomization_seed: int | None = None
    randomized_at: str | None = None


class OrgUpdate(BaseModel):
    """Update an organization."""
    name: str | None = None
    description: str | None = None
    stage: str | None = None
    funding: float | None = None
    date_funded: str | None = None
    date_founded: str | None = None
    linkedin_company_url: str | None = None
    content_source: str | None = None
    category_id: int | None = None
    content_url: str | None = None
    estimated_annual_sales: float | None = None
    employees: int | None = None
    headquarters: str | None = None
    size: int | None = None
    tier: int | None = None
    study_arm: str | None = None
    randomization_seed: int | None = None
    randomized_at: str | None = None


# -------------------------------------------------------------------------
# Patterns
# -------------------------------------------------------------------------
class PatternCreate(BaseModel):
    name: str
    description: str
    kind: str
    story: str | None = None
    taxonomy: str | None = None


class PatternUpdate(BaseModel):
    """Pattern update request body (all fields optional)."""
    name: str | None = None
    description: str | None = None
    kind: str | None = None
    story: str | None = None
    taxonomy: str | None = None


# -------------------------------------------------------------------------
# Cards
# -------------------------------------------------------------------------
class CardCreate(BaseModel):
    name: str
    description: str
    pattern_id: int
    story: str | None = None
    order_index: int | None = 0
    domain: str | None = None
    audience: str | None = None
    maturity: str | None = None


class CardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    pattern_id: int | None = None
    story: str | None = None
    order_index: int | None = None
    domain: str | None = None
    audience: str | None = None
    maturity: str | None = None


# -------------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------------
class PathNode(BaseModel):
    id: str
    type: str  # assumption, decision, state
    label: str
    serial: Optional[int] = None
    optionality: Optional[dict] = None  # {collapses: bool, reason: str}


class PathEdge(BaseModel):
    from_node: str  # node id
    to_node: str    # node id
    reason: str


class PathCreate(BaseModel):
    name: str
    nodes: list[PathNode] = []
    edges: list[PathEdge] = []


class PathUpdate(BaseModel):
    name: Optional[str] = None
    nodes: Optional[list[PathNode]] = None
    edges: Optional[list[PathEdge]] = None
    youAreHere: Optional[int] = None


# -------------------------------------------------------------------------
# Threats
# -------------------------------------------------------------------------
class ThreatCreate(BaseModel):
    name: str
    description: str
    domain: str | None = None
    tag: str | None = None
    probability: int | None = None
    damage_description: str | None = None
    spoofing: bool = False
    tampering: bool = False
    repudiation: bool = False
    information_disclosure: bool = False
    denial_of_service: bool = False
    elevation_of_privilege: bool = False
    mitigation_level: int = 0
    disabled: bool = False
    model_id: int = 1
    card_id: str | None = None


class ThreatUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    domain: str | None = None
    tag: str | None = None
    probability: int | None = None
    damage_description: str | None = None
    spoofing: bool | None = None
    tampering: bool | None = None
    repudiation: bool | None = None
    information_disclosure: bool | None = None
    denial_of_service: bool | None = None
    elevation_of_privilege: bool | None = None
    mitigation_level: int | None = None
    disabled: bool | None = None
    card_id: str | None = None

# -------------------------------------------------------------------------
# Basis threat extraction provenance
# -------------------------------------------------------------------------
class BasisRunRecord(BaseModel):
    id: int
    model_id: int
    card_id: str
    arms: list[int]
    sample_per_arm: int
    llm_model: str
    prompt_version: str
    status: str
    candidate_threat_count: int
    run_unique_candidate_threat_count: int
    new_basis_threat_count: int
    existing_basis_threat_count: int
    started_at: str
    finished_at: str | None = None
    error: str | None = None


class ThreatProvenanceRecord(BaseModel):
    id: int
    run_id: int
    threat_id: int
    product_id: int
    model_id: int
    basis_version: int
    generated_name: str
    generated_payload: dict[str, object]
    match_type: str
    match_score: float | None = None
    llm_model: str
    prompt_version: str
    source_profile_hash: str
    source_token_estimate: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    created_at: str


# -------------------------------------------------------------------------
# Models
# -------------------------------------------------------------------------
class ModelCreate(BaseModel):
    name: str
    version: str | None = None
    author: str | None = None
    company: str | None = None
    category: str | None = None
    keywords: str | None = None
    description: str | None = None


class ModelUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    author: str | None = None
    company: str | None = None
    category: str | None = None
    keywords: str | None = None
    description: str | None = None


# -------------------------------------------------------------------------
# Assets
# -------------------------------------------------------------------------
class AssetCreate(BaseModel):
    name: str
    description: str
    tag: str | None = None
    version: str | None = None
    fixed_value: float = 0
    fixed_value_period: int = 12
    recurring_value: float = 0
    include_fixed_value: bool = True
    include_recurring_value: bool = True
    disabled: bool = False
    model_id: int = 1


class AssetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tag: str | None = None
    version: str | None = None
    fixed_value: float | None = None
    fixed_value_period: int | None = None
    recurring_value: float | None = None
    include_fixed_value: bool | None = None
    include_recurring_value: bool | None = None
    disabled: bool | None = None


# -------------------------------------------------------------------------
# Vulnerabilities
# -------------------------------------------------------------------------
class VulnerabilityCreate(BaseModel):
    name: str
    description: str
    disabled: bool = False
    model_id: int = 1


class VulnerabilityUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    disabled: bool | None = None


# -------------------------------------------------------------------------
# Countermeasures
# -------------------------------------------------------------------------
class CountermeasureCreate(BaseModel):
    name: str
    description: str
    fixed_implementation_cost: int = 0
    fixed_cost_period: int = 12
    recurring_implementation_cost: int = 0
    include_fixed_cost: bool = True
    include_recurring_cost: bool = True
    implemented: bool = False
    disabled: bool = False
    model_id: int = 1


class CountermeasureUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    fixed_implementation_cost: int | None = None
    fixed_cost_period: int | None = None
    recurring_implementation_cost: int | None = None
    include_fixed_cost: bool | None = None
    include_recurring_cost: bool | None = None
    implemented: bool | None = None
    disabled: bool | None = None


# -------------------------------------------------------------------------
# Countermeasure Classes (PAT-330: Control Types)
# -------------------------------------------------------------------------
class CountermeasureClassCreate(BaseModel):
    """Create a new countermeasure control class (PAT-330)."""
    class_name: str  # e.g., "Patient Safety / Physical Harm"
    tag: str  # e.g., "PATIENT_SAFETY_PHYSICAL_HARM"
    description: str | None = None


class CountermeasureClassUpdate(BaseModel):
    """Update a countermeasure control class."""
    class_name: str | None = None
    tag: str | None = None
    description: str | None = None


class CountermeasureClassRead(BaseModel):
    """Read response for countermeasure control class."""
    id: int
    class_name: str
    tag: str
    description: str | None = None


# -------------------------------------------------------------------------
# Products (FDA-Cleared AI-Enabled Medical Devices)
# -------------------------------------------------------------------------
class ProductCreate(BaseModel):
    """Create a new FDA-cleared AI medical device product."""
    submission_number: str  # FDA 510(k) submission number (required, unique)
    device: str  # Device name (required)
    date_of_final_decision: str | None = None
    intended_use: str | None = None  # FDA-approved general function/purpose of device
    indications_for_use: str | None = None  # Specific medical conditions the device treats/diagnoses
    company: str | None = None  # Manufacturer company name
    panel: str | None = None  # FDA regulatory panel
    primary_product_code: str | None = None  # FDA product code
    product_contact_1: str | None = None  # LinkedIn profile URL
    product_contact_2: str | None = None  # LinkedIn profile URL
    product_contact_3: str | None = None  # LinkedIn profile URL
    device_description: str | None = None  # Device description from OpenFDA
    superiority: str | None = None  # Competitive advantage claims from FEELGOOD flow
    org_id: int | None = None  # Foreign key to organizations
    process_flag: bool = False  # True after the device is processed for basis-threat generation


class ProductUpdate(BaseModel):
    """Update an FDA-cleared AI medical device product."""
    submission_number: str | None = None
    device: str | None = None
    date_of_final_decision: str | None = None
    intended_use: str | None = None  # FDA-approved general function/purpose of device
    indications_for_use: str | None = None  # Specific medical conditions the device treats/diagnoses
    company: str | None = None
    panel: str | None = None
    primary_product_code: str | None = None
    product_contact_1: str | None = None
    product_contact_2: str | None = None
    product_contact_3: str | None = None
    device_description: str | None = None
    superiority: str | None = None
    org_id: int | None = None
    process_flag: bool | None = None
