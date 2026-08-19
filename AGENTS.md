# AGENTS.md

Pattern Factory's agent-driven architecture orchestrates natural language processing, data extraction, and threat modeling through a multi-workflow supervisor system. This document describes all agents, their responsibilities, decision flows, and database interactions.

## Database Connection

**Database name**: `pattern-factory` (with hyphen, not underscore)

**Always query the live database with psql, not migration scripts.** Example:
```bash
psql -d pattern-factory -c "SELECT COUNT(*) FROM threat.threats WHERE model_id = 35"
```

Schemas: `public` (patterns, products, orgs, posts, people, categories, etc.), `threat` (threats, assets, vulnerabilities, countermeasures, models, etc.)

## Rules Organization

This project uses **local AGENTS.md files** (not a centralized WARP.md) to document project-specific guidance:

- **`AGENTS.md`** (root) — Agent workflows, architecture, database interactions (you are here)
- **`src/AGENTS.md`** — Frontend UI/component patterns, accessibility, CSS classes
- **`backend/AGENTS.md`** — Backend Pydantic models, API contracts, sync rules
- **`backend/db/AGENTS.MD`** — Database schema maintenance, test suite, migration rules

When editing code, apply the rules from the file in that code's directory (and parent directories in order of precedence). Always read the relevant AGENTS.md before making structural changes.

---

## Overview

The system uses a **decision-tree workflow engine** where agents are stateless decision-makers that:
1. **Evaluate** input (message envelope, extracted context)
2. **Decide** with confidence scores (yes/no decision, 0.0–1.0 confidence)
3. **Route** to the next agent or terminal action (database upsert, SQL execution)

Six main workflows exist:
- **RULE**: Query builder (natural language → SQL → materialized view)
- **CONTENT**: Entity extraction from URLs (post, patterns, orgs, guests)
- **GENERATE**: Risk model generation from story markdown (threats, assets, vulnerabilities, countermeasures)
- **ENRICH**: Organization data enrichment (funding, revenue, valuation)
- **FEELGOOD**: Product competitive advantage extraction (FDA devices)
- **PROFILE**: FDA device profiling (intended use, device description)

---

## Agent Registry & Naming Convention

All agents follow a naming pattern: `{scope}.{AgentName}`.

**Scopes**:
- `model.*`: Decision agents (LLM-based or heuristic validation)
- `tool.*`: Terminal agents (execute database operations)

**Key Agents**:

```
model.LanguageCapo          — Pre-workflow language classification (RULE/CONTENT/CARD/ENRICH/FEELGOOD/PROFILE)
├─ RULE flow
│  ├─ model.Capo_rule                 → Validate envelope structure
│  ├─ model.verifyRequest             → Check rule logic exists
│  ├─ model.ruleToSQL                 → Convert rule to SQL via LLM
│  ├─ model.verifySQL                 → Validate SQL safety (HITL)
│  └─ tool.executeSQL                 → Create materialized view
│
├─ CONTENT flow
│  ├─ model.Capo_content              → Validate extraction request format
│  ├─ model.verifyRequest_content     → Validate URL provided
│  ├─ model.requestToExtractEntities  → Fetch + LLM extraction
│  ├─ model.verifyUpsert              → Validate entity structure
│  └─ tool.executeSQL                 → Upsert entities to database
│
├─ CARD/GENERATE flow
│  ├─ model.verifyRequest_generate    → Validate card URL format
│  ├─ model.requestToExtractRiskModel → Fetch + LLM extraction
│  ├─ model.verifyUpsertRiskModel     → Validate threat model structure
│  └─ tool.executeSQL                 → Upsert risk model to database
│
├─ ENRICH flow
│  ├─ model.validateOrgName           → Verify org exists in DB
│  ├─ model.searchForEnrichmentData   → Exa search (funding/revenue)
│  ├─ model.verifyExtractionResults   → Validate extraction
│  └─ tool.enrichOrgDatabase          → Update org record
│
├─ FEELGOOD flow
│  ├─ model.validateProductId         → Verify product exists in DB
│  ├─ model.searchForSuperiority      → Exa search (competitive advantage)
│  ├─ model.extractSuperiorityClaim   → LLM extraction
│  └─ tool.updateProductSuperiority   → Update products.superiority
│
└─ PROFILE flow
   ├─ model.validateProductId         → Verify product exists in DB
   ├─ model.searchFDADatabase         → Query FDA Devices@FDA
   ├─ model.extractDeviceProfile      → LLM extraction
   └─ tool.updateProductProfile       → Update products.intended_use + device_description
```

---

## Agent Specifications

### Pre-Workflow: Language Classification

**Agent: `model.LanguageCapo`**

**Responsibility**: Classify user intent into one of six workflows.

**Input**: 
- `message_body["raw_text"]` — Raw user message

**Decision Logic**:
1. **Fast-path recognition** (exact syntax match):
   - `"RUN <rule_code>"` → RULE
   - `"EXTRACT <url>"` → CONTENT
   - `"GENERATE <url>"` or `"CARD <url>"` → CARD
   - `"ENRICH <org_name>"` → ENRICH
   - `"FEELGOOD <product_id>"` → FEELGOOD
   - `"PROFILE <product_id>"` → PROFILE

2. **LLM classification** (if OPENAI_API_KEY set, slow path):
   - Sends message to GPT-4o-mini with router system prompt
   - Returns JSON: `{decision, verb, confidence, reason}`

3. **Heuristic fallback** (if LLM unavailable):
   - Keyword scoring for RULE, CONTENT, ENRICH, FEELGOOD, PROFILE
   - Returns highest-scoring verb

**Output**: `(decision="yes", confidence=0.55–0.98, reason, verb="RULE"|"CONTENT"|"CARD"|"ENRICH"|"FEELGOOD"|"PROFILE")`

**Special**: This is the ONLY agent that returns four values (includes `verb`).

---

## RULE Workflow (Query Builder)

Converts natural language into SQL, and creates/replaces materialized views.

### Agent: `model.Capo_rule`

**Responsibility**: Validate message envelope structure.

**Input**:
- `message_body["raw_text"]` — User request

**Checks**:
- Message is non-empty

**Output**: `(decision, confidence, reason)`

**Routing**:
- YES → `model.verifyRequest`
- NO → Return error to user

---

### Agent: `model.verifyRequest`

**Responsibility**: Validate rule logic and code.

**Input**:
- `message_body["rule_code"]` — Rule identifier (optional)
- `message_body["rule_logic"]` — Rule definition text
- `message_body["_ctx"]` — ContextBuilder (YAML rules)

**Checks**:
1. Rule logic is non-empty
2. If rule_code provided, verify it exists in YAML `RULES` array

**Note**: Does NOT validate semantic correctness (SQL table references, column names, etc.). That's LLM's job.

**Output**: `(decision, confidence, reason)`

**Routing**:
- YES → `model.ruleToSQL`
- NO → Return error (rule not found)

---

### Agent: `model.ruleToSQL`

**Responsibility**: Convert rule definition to SQL using LLM.

**Input**:
- `message_body["rule_logic"]` — Rule definition
- `message_body["_tools"]` — ToolRegistry (for sql_pitboss tool)
- `message_body["_ctx"]` — ContextBuilder (for system prompt + schema)

**Process**:
1. Build system prompt from ContextBuilder (includes schema definitions from `DATA.yaml`)
2. Call `ToolRegistry.execute("sql_pitboss", ...)` → OpenAI GPT-4o
3. Extract SQL from response

**Output**: 
- Stores `message_body["sql_query"]` with generated SQL
- Returns `(decision, confidence, reason)`

**Routing**:
- YES → `model.verifySQL` (HITL approval gate)
- NO → Return error (LLM failed to generate)

**Database Impact**: None yet.

---

### Agent: `model.verifySQL`

**Responsibility**: Validate SQL safety and syntax, request human approval (HITL).

**Input**:
- `message_body["sql_query"]` — Generated SQL

**Safety Checks**:
- SQL is non-empty
- Starts with SELECT, WITH, or INSERT (safe operations)
- No DROP, DELETE, ALTER, TRUNCATE (destructive operations)
- No SQL injection patterns (UNION, EXEC, xp_, sp_)

**Output**: 
- `(decision="no", confidence, reason)` — ALWAYS returns "no" to trigger HITL
- reason includes the SQL for user review

**Routing**:
- NO (with SQL preview) → Frontend displays approval dialog
- If approved, frontend re-sends with decision="yes" and same SQL in message_body
- NO (with rejection reason) → Return error immediately (bad SQL syntax)

**Database Impact**: None.

**Note**: The "no" decision triggers HITL pattern where frontend awaits user confirmation before proceeding.

---

### Agent: `tool.executeSQL`

**Responsibility**: Execute SQL and create materialized view. Terminal agent.

**Input**:
- `message_body["sql_query"]` — Approved SQL
- `message_body["rule_name"]` — Name for the view
- `message_body["rule_code"]` — Optional rule identifier
- `message_body["_tools"]` — ToolRegistry (for data_table and register_view)

**Process**:

**Step 1: Create Materialized View**
- Call `ToolRegistry.execute("data_table", sql_query=..., rule_name=..., rule_code=...)`
- Executes: `CREATE TABLE {rule_name}_{timestamp} AS {sql_query}`
- Returns: `table_name` (e.g., "my_rule_20250811123456"), `row_count`

**Step 2: Register Metadata**
- Call `ToolRegistry.execute("register_view", table_name=..., name=..., sql_query=...)`
- Inserts into `public.views_registry`:
  - `id`: UUID
  - `table_name`: e.g., "my_rule_20250811123456"
  - `name`: e.g., "My Rule"
  - `sql_query`: Full SQL
  - `mode`: 'explore' (default)
  - `created_at`: NOW()

**Output**: 
- Stores `message_body["table_name"]`, `message_body["row_count"]`
- Returns `(decision="yes", confidence=0.97, reason="Rule executed: view '{name}' with {N} rows")`

**Database Changes**:
- ✅ Creates new table in `public` schema
- ✅ Inserts row in `public.views_registry`
- ✅ No changes to source tables

---

## CONTENT Workflow (Entity Extraction from URLs)

Extracts posts, patterns, organizations, and guests from Substack URLs.

### Agent: `model.Capo_content`

**Responsibility**: Validate extraction request format.

**Input**:
- `message_body["raw_text"]` — User request

**Check**: Message starts with `"extract "` (case-insensitive)

**Output**: `(decision, confidence, reason)`

**Routing**:
- YES → `model.verifyRequest_content`
- NO → Return error

---

### Agent: `model.verifyRequest_content`

**Responsibility**: Validate URL is provided.

**Input**:
- `message_body["raw_text"]` — User request
- `message_body["url"]` — Optional URL (extracted from raw_text)

**Process**:
- Parse URL from `"extract <url>"` syntax
- Validate URL format (http:// or https://)

**Output**: `(decision, confidence, reason)`

**Routing**:
- YES → `model.requestToExtractEntities`
- NO → Return error (no URL)

---

### Agent: `model.requestToExtractEntities`

**Responsibility**: Fetch HTML, extract entities via LLM. Returns unverified JSON for HITL.

**Input**:
- `message_body["url"]` — Substack URL
- `message_body["_ctx"]` — ContextBuilder (for EXTRACT_CONTENT prompt from YAML)

**Process**:

1. **HTTP Fetch** (stdlib, 512KB cap):
   - User-Agent: "PatternFactoryBot/1.0"
   - Timeout: 8 seconds
   - Stores: `message_body["http_status"]`, `message_body["content_type"]`, preview

2. **LLM Extraction** (if status 200):
   - Load EXTRACT_CONTENT system prompt from `pattern-factory.yaml` CONTENT rules
   - Send payload: `{url, markup, content_source="substack"}`
   - Call GPT-4o-mini, temperature=0.2, timeout=30s
   - Extract JSON with structure:
     ```json
     {
       "orgs": [{name, description?, url?}, ...],
       "guests": [{name, description?, title?}, ...],
       "posts": [{name, description, content_url, content_source, published_at?}, ...],
       "patterns": [{name, description, kind:"pattern"|"anti-pattern"}, ...],
       "pattern_post_link": [{pattern_name, post_name}, ...],
       "pattern_org_link": [{pattern_name, org_name}, ...],
       "pattern_guest_link": [{pattern_name, guest_name}, ...]
     }
     ```

3. **Deterministic Fallback**:
   - If no posts extracted, create post from H1/H3 tags
   - Extract title, subtitle, published date via regex

**Output**:
- Stores `message_body["extracted_entities"]` with JSON
- Returns `(decision="yes", confidence=0.96, reason="Extraction complete: Post: '...', Organizations: ..., Guests: ..., Patterns: ...")`

**Routing**:
- YES → `model.verifyUpsert` (HITL review)
- NO → Return error (HTTP error, LLM failed, invalid JSON)

**Database Impact**: None yet.

---

### Agent: `model.verifyUpsert`

**Responsibility**: Validate entity extraction payload structure and referential integrity.

**Input**:
- `message_body["extracted_entities"]` — Entity JSON
- `message_body["url"]` — Source URL

**Validations**:

1. **Structural**:
   - All required arrays exist: orgs, guests, posts, patterns, pattern_*_link
   - All are lists (not objects or scalars)

2. **Required Fields**:
   - **Orgs**: name (non-empty string)
   - **Guests**: name (non-empty string)
   - **Posts**: name (non-empty string)
   - **Patterns**: name and kind (both non-empty; kind must be "pattern" or "anti-pattern")

3. **Referential Integrity**:
   - `pattern_post_link[i].post_name` → must match a `posts[j].name`
   - `pattern_org_link[i].org_name` → must match an `orgs[j].name`
   - `pattern_guest_link[i].guest_name` → must match a `guests[j].name`

4. **Safety**:
   - No SQL injection patterns (;, --, /*, */, xp_, sp_)
   - Timestamps (if present) are ISO format strings or null

**Output**: 
- Returns `(decision, confidence, reason)` with entity summary
- If invalid: `(decision="no", confidence=0.85–0.95, reason="Detailed error")`
- If valid: `(decision="yes", confidence=0.94, reason="Payload validation passed: orgs=N guests=N posts=N patterns=N")`

**Routing**:
- YES → `tool.executeSQL` (upsert)
- NO → Return error with validation details

**Database Impact**: None yet.

---

### Agent: `tool.executeSQL` (CONTENT branch)

**Responsibility**: Upsert entities to database. Terminal agent.

**Input**:
- `message_body["extracted_entities"]` — Validated entity JSON
- `message_body["_tools"]` — ToolRegistry
- `message_body["_verb"]` — "CONTENT"

**Process**:

1. Call `ToolRegistry.execute("execute_upsert", jsonb_payload=extracted_entities)`
   - Invokes stored procedure: `upsert_pattern_factory_entities(jsonb)`
   - Upserts to: `public.orgs`, `public.guests`, `public.posts`, `public.patterns`, `public.pattern_*_link` tables
   - Behavior: INSERT ... ON CONFLICT DO UPDATE (upsert by unique key)

2. Store result status in `message_body["upsert_status"]`

**Output**: `(decision="yes", confidence=0.96, reason="Content extraction and upsert complete: {url}")`

**Database Changes**:
- ✅ Upserts to `public.orgs` (by company name key)
- ✅ Upserts to `public.guests` (by name key)
- ✅ Upserts to `public.posts` (by content_url key)
- ✅ Upserts to `public.patterns` (by name+kind key)
- ✅ Upserts to pattern link tables (by composite keys)
- ✅ May trigger CASCADE updates on related records

---

## CARD/GENERATE Workflow (Risk Model Extraction from Card Markdown)

Extracts threats, assets, vulnerabilities, and countermeasures from risk model cards.

### Agent: `model.verifyRequest_generate`

**Responsibility**: Validate card URL format.

**Input**:
- `message_body["raw_text"]` — User request (e.g., "generate <url>" or "card <url>")

**Checks**:
- Card URL provided
- URL starts with http:// or https://
- URL path contains `/cards/{card_id}/story`

**Output**: 
- Stores `message_body["card_url"]`
- Returns `(decision, confidence, reason)`

**Routing**:
- YES → `model.requestToExtractRiskModel`
- NO → Return error

---

### Agent: `model.requestToExtractRiskModel`

**Responsibility**: Fetch card markdown, extract risk model entities via LLM.

**Input**:
- `message_body["card_url"]` — Card URL
- `message_body["_ctx"]` — ContextBuilder (for GEN_RISK_MODEL prompt from YAML)

**Process**:

1. **Parse card_id from URL**:
   - Extract from `/cards/{card_id}/story` path structure
   - Stores in `message_body["card_id"]`

2. **Fetch Active Model**:
   - HTTP GET `/active-model` → retrieve `model_id` from `public.active_models`
   - Stores in message_body for next agent

3. **Fetch Card Markdown**:
   - HTTP GET to card_url (httpx, timeout=10s, async)
   - Stores raw markdown

4. **LLM Extraction** (GPT-5.5 for superior structured extraction):
   - Load GEN_RISK_MODEL system prompt from `pattern-factory.yaml` CONTENT rules
   - Send payload: `{story, model_id, card_id}`
   - Call GPT-5.5 (temperature=1.0, only supported value), timeout=300s
   - Extract JSON:
     ```json
     {
       "assets": [{tag, name, description?, fixed_value, recurring_value}, ...],
       "threats": [{tag, name, domain, probability, description?}, ...],
       "vulnerabilities": [{name, description?, severity?}, ...],
       "countermeasures": [{tag, name, description?, status?}, ...],
       "asset_threat": [{asset_tag, threat_tag}, ...],
       "vulnerability_threat": [{vulnerability_name, threat_tag}, ...],
       "countermeasure_threat": [{countermeasure_tag, threat_tag}, ...]
     }
     ```

5. **Add Context**:
   - Append `model_id` and `card_id` to extracted_entities

**Output**:
- Stores `message_body["extracted_entities"]` with risk model JSON
- Returns `(decision="yes", confidence=0.96, reason="Extraction complete: Assets: ..., Threats: ..., Vulnerabilities: ..., Countermeasures: ...")`

**Routing**:
- YES → `model.verifyUpsertRiskModel`
- NO → Return error (fetch failed, LLM failed)

**Database Impact**: None yet.

---

### Agent: `model.verifyUpsertRiskModel`

**Responsibility**: Validate risk model payload structure and referential integrity.

**Input**:
- `message_body["extracted_entities"]` — Risk model JSON

**Validations**:

1. **Required Fields**:
   - `model_id` and `card_id` present and non-empty

2. **Structural**:
   - All required arrays exist and are lists

3. **Entity Requirements**:
   - **Assets**: tag, name, fixed_value (numeric ≥ 0), recurring_value (numeric ≥ 0); tags unique
   - **Threats**: tag, name, domain, probability; tags unique
   - **Vulnerabilities**: name (non-empty)
   - **Countermeasures**: name (non-empty)

4. **Referential Integrity**:
   - `asset_threat[i].asset_tag` → must exist in assets
   - `asset_threat[i].threat_tag` → must exist in threats
   - `vulnerability_threat[i].vulnerability_name` → must exist in vulnerabilities
   - `vulnerability_threat[i].threat_tag` → must exist in threats
   - `countermeasure_threat[i].countermeasure_tag` → must exist in countermeasures
   - `countermeasure_threat[i].threat_tag` → must exist in threats

5. **Safety**: No SQL injection patterns

**Output**: 
- Returns `(decision, confidence, reason)` with entity summary
- If valid: `(decision="yes", confidence=0.94, reason="Payload validation passed: assets=N threats=N vulns=N cms=N")`

**Routing**:
- YES → `tool.executeSQL` (upsert)
- NO → Return error with validation details

**Database Impact**: None yet.

---

### Agent: `tool.executeSQL` (CARD branch)

**Responsibility**: Upsert risk model to database. Terminal agent.

**Input**:
- `message_body["extracted_entities"]` — Validated risk model JSON
- `message_body["_tools"]` — ToolRegistry
- `message_body["_verb"]` — "GENERATE"

**Process**:

1. Call `ToolRegistry.execute("execute_risk_model_upsert", jsonb_payload=extracted_entities)`
   - Invokes stored procedure: `threat.upsert_risk_model(jsonb)`
   - Upserts to threat schema tables:
     - `threat.assets` (by tag)
     - `threat.threats` (by tag, scoped to model_id)
     - `threat.vulnerabilities` (by name, scoped to model_id)
     - `threat.countermeasures` (by tag, scoped to model_id)
     - `threat.asset_threat`, `threat.vulnerability_threat`, `threat.countermeasure_threat` (link tables)
   - Links to card via `threat.cards` table (card_id, model_id, created_at)

2. Store result summary

**Output**: `(decision="yes", confidence=0.96, reason="Risk model generation and upsert complete: model_id={id}, card_id={id}")`

**Database Changes**:
- ✅ Upserts to `threat.assets`, `threat.threats`, `threat.vulnerabilities`, `threat.countermeasures`
- ✅ Upserts to link tables (`threat.asset_threat`, etc.)
- ✅ Inserts into `threat.cards` (card metadata)
- ✅ Scoped to `threat` schema (isolated from public patterns)

---

## ENRICH Workflow (Organization Data Enrichment)

Enriches organization records with funding, revenue, and valuation data.

### Agent: `model.validateOrgName`

**Responsibility**: Verify organization exists in database.

**Input**:
- `message_body["raw_text"]` — User request (e.g., "enrich acme corp")
- `message_body["_tools"]` — ToolRegistry (database access)

**Process**:
1. Extract org name from message
2. Query `public.orgs` table for matching name
3. Validate org found

**Output**: 
- Stores `message_body["org_id"]`
- Returns `(decision, confidence, reason)`

**Routing**:
- YES → `model.searchForEnrichmentData`
- NO → Return error (org not found)

---

### Agent: `model.searchForEnrichmentData`

**Responsibility**: Search web for funding/revenue data using Exa.

**Input**:
- `message_body["org_id"]` — Organization ID
- Org details (name, description)

**Process**:
1. Build Exa search queries:
   - `"{org_name} funding announcement"`
   - `"{org_name} annual revenue"`
   - `"{org_name} valuation"`
2. Execute searches (Exa API):
   - **CRITICAL**: Use `contents={\"highlights\": True}` (not `highlights=True` parameter)
   - Use `type="auto"` (not "neural")
   - Use `num_results` (not `numResults`)
   - Pattern: `exa.search(query, num_results=10, type="auto", contents={\"highlights\": True})`
3. Collect results with highlights
4. Store in `message_body["search_results"]`

**Output**: 
- Returns `(decision="yes", confidence, reason="Found {N} funding sources, {N} revenue references, ...")`

**Routing**:
- YES → `model.verifyExtractionResults`
- NO → Return error (no results)

**Database Impact**: None yet.

---

### Agent: `model.verifyExtractionResults`

**Responsibility**: Validate extracted data before database update.

**Input**:
- `message_body["search_results"]` — Exa results with extracted data

**Process**:
- Validate funding/revenue/valuation data structure
- Check for valid numbers (currency, etc.)
- Validate source URLs

**Output**: `(decision, confidence, reason)`

**Routing**:
- YES → `tool.enrichOrgDatabase`
- NO → Return error (invalid data)

---

### Agent: `tool.enrichOrgDatabase`

**Responsibility**: Update org record in database. Terminal agent.

**Input**:
- `message_body["org_id"]` — Organization ID
- Enrichment data (funding_source, annual_revenue, valuation, etc.)

**Database Changes**:
- ✅ UPDATE `public.orgs` SET funding_source=..., annual_revenue=..., valuation=..., updated_at=NOW()
- ✅ INSERT into `public.system_log` (event, context) with enrichment details

**Output**: `(decision="yes", confidence=0.95, reason="Organization enriched: {org_name} – funding: {source}, revenue: {value}, valuation: {value}")`

---

## FEELGOOD Workflow (Product Competitive Advantage)

Extracts competitive advantage claims for FDA-cleared AI-enabled medical devices.

### Agent: `model.validateProductId`

**Responsibility**: Verify product exists in database.

**Input**:
- Product ID or submission_number from message

**Process**:
1. Query `public.products` table
2. Validate product found

**Output**: 
- Stores `message_body["product_id"]`
- Returns `(decision, confidence, reason)`

**Routing**:
- YES → `model.searchForSuperiority`
- NO → Return error (product not found)

**Database Query**: 
```sql
SELECT id, submission_number, device, company, indicated_use, device_description 
FROM public.products 
WHERE id = ? OR submission_number = ?
```

---

### Agent: `model.searchForSuperiority`

**Responsibility**: Search web for competitive advantage claims using Exa.

**Input**:
- `message_body["product_id"]`
- Product details (company, device, indicated_use, device_description)

**Process**:
1. Build Exa search queries:
   - `"{company} {device} competitive advantage"`
   - `"{device} superior to"`
   - `"{indicated_use} {company} advantage"`
2. Execute searches with **correct Exa API usage**:
   ```python
   exa.search(
     query="...",
     num_results=10,
     type="auto",
     contents={"highlights": True}  # CORRECT: dict, not parameter
   )
   ```
3. Collect results with highlights

**Output**: 
- Stores `message_body["search_results"]`
- Returns `(decision="yes", confidence, reason="Found {N} competitive advantage references")`

**Routing**:
- YES → `model.extractSuperiorityClaim`
- NO → Return error (no results)

**Database Impact**: None yet.

---

### Agent: `model.extractSuperiorityClaim`

**Responsibility**: Extract and validate superiority claims via LLM.

**Input**:
- `message_body["search_results"]` — Exa search results
- Product context

**Process**:
1. Use GPT-4o-mini (temperature=0.0 for deterministic extraction)
2. Extract claim: "What is the key competitive advantage?"
3. Validate claim is non-empty and specific to product

**Output**: 
- Stores `message_body["superiority_claim"]`
- Returns `(decision="yes", confidence, reason="Extracted claim: '{claim}'")`

**Routing**:
- YES → `tool.updateProductSuperiority`
- NO → Return error (LLM failed)

**Database Impact**: None yet.

---

### Agent: `tool.updateProductSuperiority`

**Responsibility**: Update product superiority in database. Terminal agent.

**Input**:
- `message_body["product_id"]` — Product ID
- `message_body["superiority_claim"]` — Extracted claim

**Database Changes**:
- ✅ UPDATE `public.products` SET superiority = '{claim}', updated_at = NOW() WHERE id = ?
- ✅ INSERT into `public.system_log` (event, context) with update details

**Output**: `(decision="yes", confidence=0.96, reason="Product {device} superiority updated: '{claim}'")`

---

## PROFILE Workflow (FDA Device Profiling)

Populates device description and intended use from FDA official sources.

### Agent: `model.validateProductId` (shared with FEELGOOD)

Same as FEELGOOD workflow.

---

### Agent: `model.searchFDADatabase`

**Responsibility**: Query FDA Devices@FDA for official device profiles.

**Input**:
- Product ID or submission_number

**Process**:
1. Extract submission_number from product record
2. Construct FDA Devices@FDA URL:
   - For 510(k): `https://www.fda.gov/cdrh/devicesatfda/?mode=simple&value={submission_number}`
   - For PMA: Similar pattern for premarket approval docs
3. Fetch official clearance document (future: parse PDF)

**Output**: 
- Stores `message_body["fda_document"]` (URL or content)
- Returns `(decision, confidence, reason)`

**Routing**:
- YES → `model.extractDeviceProfile`
- NO → Return error (FDA lookup failed)

---

### Agent: `model.extractDeviceProfile`

**Responsibility**: Extract intended use and device description from FDA document.

**Input**:
- `message_body["fda_document"]` — FDA clearance document (URL or text)
- Product context

**Process**:
1. Use GPT-4o-mini to extract:
   - **Intended Use**: General function/purpose from clearance summary
   - **Device Description**: Technical specifications
2. Validate both fields are non-empty
3. Store in message_body

**Output**: 
- Stores `message_body["intended_use"]`, `message_body["device_description"]`
- Returns `(decision="yes", confidence, reason="Extracted intended use and device description")`

**Routing**:
- YES → `tool.updateProductProfile`
- NO → Return error (extraction failed)

**Database Impact**: None yet.

---

### Agent: `tool.updateProductProfile`

**Responsibility**: Update product with FDA data. Terminal agent.

**Input**:
- `message_body["product_id"]` — Product ID
- `message_body["intended_use"]` — FDA intended use text
- `message_body["device_description"]` — Technical description

**Database Changes**:
- ✅ UPDATE `public.products` SET intended_use = ?, device_description = ?, updated_at = NOW() WHERE id = ?
- ✅ INSERT into `public.system_log` with profile update details

**Output**: `(decision="yes", confidence=0.96, reason="Product {device} profile updated with FDA intended use and device description")`

---

## Message Protocol & HITL (Human-In-The-Loop)

Agents communicate via **MessageEnvelope** protocol.

### Envelope Structure

```json
{
  "type": "request" | "response" | "error",
  "version": "1.1",
  "session_id": "sess-...",
  "request_id": "req-...",
  "verb": "RULE" | "CONTENT" | "GENERATE" | "ENRICH" | "FEELGOOD" | "PROFILE",
  "nextAgent": "agent-name" | null,
  "decision": "yes" | "no" | null,
  "confidence": 0.0-1.0,
  "reason": "explanation",
  "returnCode": 0 | 1 | -1,
  "messageBody": { 
    "raw_text": "...",
    "extracted_entities": {...},
    "sql_query": "...",
    "_tools": ToolRegistry,
    "_ctx": ContextBuilder,
    "_verb": "RULE"|"CONTENT"|...,
    ...
  }
}
```

### HITL Pattern

**When a decision returns "no" with confidence < 0.95:**

1. **Frontend detects HITL state** (decision="no" + relevant context in reason)
2. **User reviews** (SQL preview, extracted entities, etc.)
3. **User provides feedback** (approval, rejection, modification)
4. **Frontend re-sends** with:
   - Same `verb` and `nextAgent` (NO MODIFICATION)
   - Updated `messageBody` with user feedback
   - Optional `raw_text` with user comments
5. **Backend routes** directly to stored `nextAgent` (skips classification)
6. **Agent processes** user feedback and decides again

**Example (RULE workflow)**:
```
1. model.ruleToSQL returns SQL
2. model.verifySQL returns decision="no" with SQL in reason (HITL)
3. Frontend shows approval dialog
4. User clicks "Approve"
5. Frontend re-sends with same envelope, nextAgent="tool.executeSQL"
6. tool.executeSQL executes the approved SQL
```

---

## Database Schema & Agent Interactions

### Public Schema (Explore Mode)

| Table | Agents | Operations |
|-------|--------|-----------|
| `orgs` | validateOrgName, requestToExtractEntities, enrichOrgDatabase | SELECT, INSERT, UPDATE |
| `guests` | requestToExtractEntities, verifyUpsert | SELECT, INSERT, UPDATE |
| `posts` | requestToExtractEntities, verifyUpsert | SELECT, INSERT, UPDATE |
| `patterns` | requestToExtractEntities, verifyUpsert | SELECT, INSERT, UPDATE |
| `pattern_*_link` | requestToExtractEntities, verifyUpsert | SELECT, INSERT, UPDATE |
| `products` | validateProductId, searchForSuperiority, searchFDADatabase, updateProductSuperiority, updateProductProfile | SELECT, UPDATE |
| `views_registry` | executeSQL (RULE) | INSERT, SELECT |
| `active_models` | requestToExtractRiskModel | SELECT |
| `system_log` | enrichOrgDatabase, updateProductSuperiority, updateProductProfile, executeSQL | INSERT |

### Threat Schema (Model Mode)

| Table | Agents | Operations |
|-------|--------|-----------|
| `models` | requestToExtractRiskModel | SELECT |
| `assets` | requestToExtractRiskModel, verifyUpsertRiskModel, executeSQL (CARD) | SELECT, INSERT, UPDATE |
| `threats` | requestToExtractRiskModel, verifyUpsertRiskModel, executeSQL (CARD) | SELECT, INSERT, UPDATE |
| `vulnerabilities` | requestToExtractRiskModel, verifyUpsertRiskModel, executeSQL (CARD) | SELECT, INSERT, UPDATE |
| `countermeasures` | requestToExtractRiskModel, verifyUpsertRiskModel, executeSQL (CARD) | SELECT, INSERT, UPDATE |
| `asset_threat` | executeSQL (CARD) | INSERT, UPDATE |
| `vulnerability_threat` | executeSQL (CARD) | INSERT, UPDATE |
| `countermeasure_threat` | executeSQL (CARD) | INSERT, UPDATE |
| `cards` | executeSQL (CARD) | INSERT |

---

## Execution Model

### Agent Execution Context

Each agent receives `message_body` dictionary with:
- **User Input**: `raw_text`, `url`
- **Extracted Context**: `sql_query`, `extracted_entities`, `search_results`
- **Internal Dependencies**: `_tools` (ToolRegistry), `_ctx` (ContextBuilder), `_verb` (workflow verb)
- **Metadata**: `session_id`, `request_id`

### Async/Await Pattern

All agents are async functions:
```python
async def agent_name(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    # decision, confidence, reason
```

Async operations (HTTP, OpenAI, database) use:
- `asyncio.to_thread()` for blocking I/O (urllib, httpx)
- Native async for FastAPI database operations (asyncpg)

### Timeout & Resource Limits

| Operation | Timeout | Limit |
|-----------|---------|-------|
| HTTP fetch (HTML) | 8s | 512 KB |
| HTTP fetch (card markdown) | 10s | unlimited |
| OpenAI API (extraction) | 30s | gpt-4o-mini |
| OpenAI API (risk model) | 300s (5m) | gpt-5.5 |
| Exa search | 15s | 10 results per query |
| SQL execution | 60s | 1000000 rows |

---

## Error Handling & Fallback Strategies

### LLM Unavailable

If `OPENAI_API_KEY` is not set:
- `model.LanguageCapo` → Falls back to heuristic keyword scoring
- Entity extraction agents → Return error (cannot proceed)

### Network Failures

- HTTP fetch timeout → Return error with status
- Exa API failure → Return error, suggest retry
- FDA lookup failure → Return error, user can retry later

### Database Errors

- Upsert conflict → Let stored procedure handle (UPDATE if exists)
- Foreign key violation → Validation agent should catch before upsert
- Connection pool exhausted → Return error, frontend suggests retry

### Invalid Extraction

- LLM returns non-JSON → Parse error, return error message
- Required fields missing → Validation agent catches before upsert
- Referential integrity broken → Validation agent catches before upsert

---

## Logging & Observability

### System Log Table

```sql
CREATE TABLE public.system_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event TEXT NOT NULL,
  context JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Usage**: Use `logging_util.log_event()` for ALL event logging.

**WRONG**:
```python
INSERT INTO system_log (event_type, entity_table, entity_id, details)
VALUES ('entity_upserted', 'patterns', 123, '...')
```

**RIGHT**:
```python
logging_util.log_event("entity_upserted", {
  "entity_table": "patterns",
  "entity_id": 123,
  "details": "..."
})
```

### Agent Logging

Each agent logs decision with confidence:
```
🤖 [model.Capo] Validating message envelope...
  Decision: yes (confidence: 1.0)
```

---

## Performance Considerations

### Async Operations

- **HTTP fetch + LLM**: Runs in parallel via `asyncio.to_thread()` for I/O-bound operations
- **Upsert operations**: Use batch inserts in stored procedures (not individual rows)
- **Search operations**: Cache Exa results in message_body to avoid duplicate searches

### Database Indexes

Required indexes (verify exist):
- `public.orgs(name)` — For org lookup by name
- `public.guests(name)` — For guest lookup
- `public.posts(content_url)` — For post deduplication
- `public.patterns(name, kind)` — For pattern lookup
- `public.products(submission_number, company)` — For product lookup
- `threat.assets(tag, model_id)` — For asset lookup by tag within model
- `threat.threats(tag, model_id)` — For threat lookup

---

## Testing Agents

### Unit Testing

```bash
# Run agent tests
pytest backend/tests/test_agents.py -v

# Test specific agent
pytest backend/tests/test_agents.py::test_agent_language_capo -v
```

### Integration Testing

```bash
# Start backend
uvicorn services.api:app --reload

# Send WebSocket message
wscat -c ws://localhost:8000/ws
> {"type":"request", "verb":"RULE", "nextAgent":"model.LanguageCapo", ...}
```

### CLI Tools (Batch Processing)

```bash
# ENRICH flow
./bin/enrich acme_corp

# FEELGOOD flow
./bin/feelgood --product-ids=1,5,10

# PROFILE flow
./bin/profile --product-ids=1,5,10
```

---

## Common Patterns & Best Practices

### 1. Database Queries in Agents

Use ToolRegistry for database access (not direct asyncpg):
```python
result = await tool_registry.execute("query_products", id=product_id)
```

### 2. HTTP Requests

Use asyncio.to_thread() for blocking urllib:
```python
text, status, ctype = await _http_get_text(url)
```

Or use httpx for async:
```python
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

### 3. LLM Calls

Always use GPT-4o-mini unless specified otherwise (cost):
```python
response = await _call_openai_async(
    client=client,
    system_prompt=system_prompt,
    user_message=user_message,
    model="gpt-4o-mini",  # Default for most agents
    temperature=0.0,       # Deterministic extraction
    timeout=30.0
)
```

### 4. Validation Patterns

Validate in agents BEFORE database writes:
- Structural validity (required arrays, objects)
- Required fields (non-empty strings, valid enums)
- Referential integrity (link table references)
- Safety (SQL injection, XSS patterns)

### 5. Error Messages

Return actionable error reasons:
```python
# GOOD
reason = "Post at index 2 missing 'name' field"

# BAD
reason = "Invalid data"
```

---

## Future Enhancements

1. **Agent Caching**: Cache LLM responses for identical rule logic
2. **Batch Processing**: Optimize FEELGOOD/PROFILE flows for 100+ products
3. **Streaming Responses**: Stream LLM results to frontend as they arrive
4. **Agent Metrics**: Track per-agent success rates, confidence distributions
5. **Dynamic Agent Loading**: Load custom agents from Python modules at runtime
6. **New agent flows**: Add more agent workflows as needed

## Iteration & Error Handling Rules
- If a terminal command fails, analyze the root cause before changing files.
- Never write a patch that bypasses our core typing or architectural rules.
- If a fix requires modifying an external module, ask for permission first.
- Always check if the function you are writing already exists in the codebase.

## 1. High-ROI System Commands
- always reference environment variables in .env file in project root
- always place markdown files you create in the /docs directory

## 2. Structural & Architectural Invariants
- Styling: use src/app.css and src/main.css. Never install inline style packages.
- API Layer: All client data fetching must route through custom hooks inside `/src/hooks/queries`.

## 3. The Three-Tier Boundary Model
<!-- Defining strict "Never" rules cuts down on hallucinated files and breaking changes -->
### Always Do
- Write comprehensive TypeScript types when introducing new columns in the database avoid using `any`.
- Update Pydantic models when introducing new columns in the database
- Keep components under 150 lines. Extract sub-logic aggressively.
- Always reference db schema using psql - do not use migration files

### Ask First
- Before adding any new external dependencies to `package.json`.
- Before modifying shared components inside `/components/ui/`.

### Never Do
- Never use placeholder or truncation comments like `// TODO: Implement later`.

## Commit Message Convention

- Start every commit subject with its Linear issue ID: `PAT-XXX: <imperative summary>` (e.g. `PAT-308: fix profile agent entity resolution via direct FDA retrieval`).
- Use a colon plus one space between the ID and the summary; write the summary in imperative mood, ~72 chars or fewer.
- For commits spanning multiple issues, lead with the primary ID and list the rest in the body.
- Create or locate a Linear issue before committing work that has none — avoid commits with no issue ID.

