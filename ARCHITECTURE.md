# Pattern Factory — Architecture & Engineering Reference

> Single source of truth for the system architecture, module responsibilities, API contracts, data flows, known technical debt, and the engineering constraints that must be honored in future refactoring.
>
> Companion documents: `WARP.md` (agent/AI workflow detail), `CONSISTENT_UI_GUIDE.md` (UI patterns), `REFACTORING_SUMMARY.md` (prior refactor history).

## Table of Contents

1. [System Architecture Map](#1-system-architecture-map)
2. [Core Module Responsibilities](#2-core-module-responsibilities)
3. [Key API Contracts](#3-key-api-contracts)
4. [Major Data Flows](#4-major-data-flows)
5. [Core Call Chains](#5-core-call-chains)
6. [Potential Technical Debt](#6-potential-technical-debt)
7. [Engineering Constraints for Future Refactoring](#7-engineering-constraints-for-future-refactoring)

---

## 1. System Architecture Map

Pattern Factory is a full-stack application with three logical layers: a **SvelteKit frontend**, a **FastAPI backend**, and an **AI-driven "Pitboss" supervisor** that orchestrates LLM agents over WebSockets, all backed by **PostgreSQL 17**.

The system has two distinct interaction surfaces:

- **Synchronous REST** — CRUD for all entities (patterns, cards, paths, threats, assets, models, etc.) and a generic table reader.
- **Asynchronous WebSocket** — the Pitboss message protocol (v1.1) that drives AI-driven rule→SQL→execute and content-extraction flows with human-in-the-loop (HITL) gating.

```mermaid
flowchart LR
  subgraph Frontend["SvelteKit Frontend (Svelte 5)"]
    Layout["+layout.svelte"]
    Header["Header.svelte<br/>mode selector"]
    Sidebar["Sidebar.svelte<br/>mode-aware nav + views"]
    Chat["ChatDrawer/Interface<br/>WebSocket client"]
    Pages["Routes: patterns, cards,<br/>paths, models, threats,<br/>assets, vulns, CMs, bigpicture"]
    Stores["modeStore / searchStore<br/>localStorage-backed"]
  end

  subgraph Backend["FastAPI Backend (services/api.py)"]
    REST["REST CRUD endpoints"]
    WS["/ws WebSocket"]
    Query["/query/{table}<br/>/views?mode="]
  end

  subgraph Pitboss["Pitboss AI Supervisor (backend/pitboss)"]
    Sup["Supervisor<br/>process_envelope"]
    WF["WorkflowEngine<br/>RULE/CONTENT/GENERATE trees"]
    Agents["Agents<br/>LanguageCapo, Capo, verifyRequest,<br/>ruleToSQL, verifySQL, executeSQL,<br/>extractEntities, extractRiskModel"]
    Ctx["ContextBuilder<br/>YAML hot-reload"]
    Tools["ToolRegistry<br/>sql_pitboss, data_table,<br/>register_view, execute_upsert,<br/>execute_risk_model_upsert"]
  end

  subgraph DB["PostgreSQL 17"]
    PF["public: patterns, cards, paths,<br/>views_registry, users, active_models"]
    TH["threat: models, threats, assets,<br/>vulnerabilities, countermeasures,<br/>junction tables, views, functions"]
    SL["system_log"]
  end

  subgraph External["External"]
    OpenAI["OpenAI GPT-4o / gpt-4o-mini"]
    Google["Google Charts (CDN)"]
  end

  Layout --> Header & Sidebar & Chat & Pages
  Pages & Stores -->|HTTP fetch| REST & Query
  Chat -->|WebSocket JSON envelopes| WS
  WS --> Sup
  Sup --> WF & Agents & Ctx & Tools
  Agents -->|chat.completions| OpenAI
  Tools --> DB
  REST --> DB
  Pages -->|google.charts| Google
```

### Technology Stack

| Layer | Technology |
|---|---|
| Frontend framework | Svelte 5 (runes) + SvelteKit, TypeScript |
| Frontend styling | Plain CSS in `app.css` / `main.css` (Tailwind removed) |
| Frontend tables/charts | DataTables.net, Google Charts (CDN) |
| Backend framework | FastAPI (async), Python 3 |
| DB driver | asyncpg (pooled, min 1 / max 5) |
| AI / LLM | OpenAI GPT-4o (SQL gen), gpt-4o-mini (classification) |
| Realtime | WebSocket (`/ws`) — Message Protocol v1.1 |
| Database | PostgreSQL 17 (schemas: `public`, `threat`) |

---

## 2. Core Module Responsibilities

### Frontend (`src/`)

| Module | Responsibility |
|---|---|
| `routes/+layout.svelte` | App shell: renders `Header` + `Sidebar` + `ChatDrawer` + page children. Owns chat drawer open state. |
| `lib/Header.svelte` | Brand, mode selector (Explore/Model), active model name display, global search input, chat button. `switchMode` switches mode and navigates to `/patterns` or `/models`. |
| `lib/Sidebar.svelte` | Mode-aware navigation (3+3 paradigm: Explore = Patterns/Stories/Paths; Model = Models/Threats/Assets) plus a "Views" section fetched from `/views?mode=`. Refreshes on the `views:refresh` window event. |
| `lib/modeStore.ts` | Svelte writable store persisted to `localStorage` (`pf:mode`, `pf:activeModel`, `pf:activeModelName`). `switchMode('model')` fetches the active model from the backend. |
| `lib/searchStore.ts` | Global search term store used by index pages for client-side filtering. |
| `lib/ChatInterface.svelte` | WebSocket client (`ws://localhost:8000/ws`). Builds Message Protocol v1.1 envelopes, handles responses, detects HITL (`decision === 'no'` + `nextAgent`), echoes `messageBody` back on resume. Dispatches `views:refresh` events to the window. |
| `lib/AssetDetail.svelte`, `ThreatDetail.svelte`, `EntityDetailLayout.svelte`, `CheckboxField.svelte`, `SingleSelect.svelte` | Reusable entity view/edit components enforcing the consistent UI pattern. |
| `lib/db.ts` | TypeScript interfaces (`Pattern`, `Card`, `Threat`, `Asset`, `Vulnerability`, `Countermeasure`, `Model`, `Path`) and fetch helpers. |
| `src/routes/*` | SvelteKit file-based routing. Each entity has `+page.svelte` (index), `[id]/+page.svelte` (view), `[id]/edit/+page.svelte` (edit). |

### Backend API (`backend/services/api.py`)

Single FastAPI module that owns:

- FastAPI app + CORS (`allow_origins=["*"]` — dev only).
- asyncpg connection pool (min 1, max 5) created on startup.
- Pydantic `Create` / `Update` models for every entity.
- Full CRUD endpoints for patterns, cards, paths, threats, models, assets, vulnerabilities, countermeasures.
- Mode-aware endpoints: `GET /views?mode=`, `POST /models/{id}/activate`, `GET /active-model`.
- Generic reader: `GET /query/{table}` (sanitized, quotes table name).
- WebSocket `/ws` → instantiates `PitbossSupervisor` and routes envelopes vs legacy `run_rule`.
- `POST /log` → `system_log` table.
- Hardcoded `CURRENT_USER_ID` stub (no real auth/session).

### Pitboss (`backend/pitboss/`)

| Module | Responsibility |
|---|---|
| `supervisor.py` | `PitbossSupervisor.process_envelope()` — entry point. Validates verb, handles HITL resume (jumps to `env.nextAgent`), classifies new messages via `LanguageCapo`, walks the workflow decision tree, sends each step as a response envelope, emits `views:refresh` on successful RULE termination. Strips internal `_`-prefixed keys before sending to frontend. |
| `workflow.py` | `WorkflowEngine` — hardcoded decision trees for RULE, CONTENT, GENERATE verbs. Each node has `branch_yes` / `branch_no`. `get_hitl_next_agent()` maps resume targets (e.g., RULE `verifySQL` → `tool.executeSQL`). |
| `agents.py` | Agent functions returning `(decision, confidence, reason)` (`LanguageCapo` returns a 4-tuple with verb). Includes `LanguageCapo` (router with RUN / GENERATE / CARD / EXTRACT fast-paths + LLM / heuristic fallback), `agent_capo_rule`, `agent_verify_request`, `agent_verify_request_generate` (validates `/cards/{id}/story` URLs), rule→SQL, verifySQL, entity extraction, risk model extraction. DI via `message_body['_tools']` and `message_body['_ctx']`. |
| `tools.py` | `ToolRegistry` + tools: `SqlPitbossTool` (LLM→SQL via OpenAI, runs in thread pool), `DataTableTool` (DROP/CREATE VIEW from SELECT), `RegisterViewTool` (UPSERT into `views_registry` on `table_name`), `ExecuteUpsertTool` (`CALL upsert_pattern_factory_entities`), `ExecuteRiskModelUpsertTool` (`CALL threat.upsert_risk_model`). |
| `context_builder.py` | Loads `SYSTEM/DATA/RULES/CAPO/CONTENT.yaml` from `prompts/rules/` with per-file mtime hot-reload. Assembles the system prompt + DATA schema for the LLM. |
| `envelope.py` | `MessageEnvelope` dataclass + `MessageType` / `Verb` / `Decision` enums + `make_request/response/error/success` helpers. Protocol v1.1. |
| `config.py` | Model config (gpt-4o, temp 0.2, max_tokens 400), workflow config (`max_feedback_loops 3`, `auto_approve_threshold 0.95`, `enable_human_review`), DB / tool toggles. `adjust_temperature_for_task` mapping. |

### Database (`backend/db/`)

- `pattern_factory_schema.sql` / `upsert_pattern_factory_entities.sql` — `public` schema: `patterns`, `cards`, `paths`, `episodes`, `guests`, `orgs`, `posts`, junction tables, `views_registry`, `users`, `active_models`.
- `threat_schema.sql` — `threat` schema: `projects`, `areas`, `assets`, `threats`, `vulnerabilities`, `countermeasures`, `entrypoints`, `attacker_types`, and junction tables (`asset_threat`, `countermeasure_threat`, `vulnerability_threat`, `pattern_threat`, etc.).
- `20260204-var.sql` — analytical views: `threat.threat_impact` (VaR before / after mitigation, residual risk), `threat.threat_countermeasures`, `threat.asset_threat_exploitability`. These views filter by `public.active_models`.
- `20260701-mitigation-level-function.sql` — PLpgSQL function `threat.compute_mitigation_level(threat_id)` + triggers that auto-populate `threats.mitigation_level` from the `threat_impact` view.
- Migration files are date-prefixed (`YYYYMMDD-*.sql`) and run in alphanumeric order. Each is wrapped in `BEGIN/COMMIT`.

---

## 3. Key API Contracts

### REST contracts

All return JSON. Validation failures and missing rows raise `HTTPException` (400 or 404). Deletes return `{"status":"ok","deleted_id":id}`.

| Method | Path | Contract |
|---|---|---|
| `GET` | `/patterns`, `/cards`, `/paths`, `/threats`, `/assets`, `/vulnerabilities`, `/countermeasures`, `/models` | Returns `Row[]`. Threats / assets / vulns / CMs read from `threat.v*` views (model-scoped). |
| `POST` | `/{entity}` | Accepts `*Create` Pydantic model, returns created row. Cards verify `pattern_id` exists. |
| `GET` | `/{entity}/{id}` | Returns single row. `GET /threats/{id}` joins card details when `card_id` is present. |
| `PUT` | `/{entity}/{id}` | Accepts `*Update` with all-optional fields, uses `COALESCE($n, col)` patch semantics. Threats use a dynamic per-field query builder instead. |
| `DELETE` | `/{entity}/{id}` | Returns `{"status":"ok","deleted_id":id}` or 404. |
| `GET` | `/patterns/search?q=`, `/threats/search?q=` | ILIKE autocomplete, limit 50. |
| `GET` | `/views?mode=explore\|model` | Filters `views_registry` by the `mode` column. |
| `GET` | `/query/{table}?limit=` | Generic reader. Table name is sanitized (`replace("_","").isalnum()`) and quoted in SQL. |
| `POST` | `/models/{id}/activate` | Upserts `public.active_models (user_id, model_id)` for `CURRENT_USER_ID`. |
| `GET` | `/active-model` | Returns `{"model_id": int\|null}`. |
| `POST` | `/log` | Inserts into `system_log`. |

### WebSocket contract — Message Protocol v1.1

Envelope shape (defined in `backend/pitboss/envelope.py`):

```json path=null start=null
{
  "type": "request" | "response" | "error",
  "version": "1.1",
  "timestamp": 1234567890,
  "session_id": "session-abc",
  "request_id": "req-1",
  "verb": "RULE" | "CONTENT" | "CARD" | "GENERATE" | "GENERIC",
  "nextAgent": "model.Capo" | null,
  "returnCode": 0 | 1 | -1,
  "decision": "yes" | "no" | null,
  "confidence": 0.0,
  "reason": "...",
  "messageBody": { }
}
```

**Put-and-take rules (critical contract):**

1. Frontend sends a REQUEST with `verb: GENERIC`, `nextAgent: model.LanguageCapo`.
2. Backend returns a RESPONSE with `nextAgent` set; the frontend MUST echo it back unchanged.
3. Frontend echoes `messageBody` from the backend response (preserving `sql_query`, `rule_code`, etc.) and may add `raw_text`.
4. On `decision: "no"` → HITL. Frontend stores the full `messageBody` and, on user reply, resends with the SAME `verb` and SAME `nextAgent`. Backend routes directly to `nextAgent` without reclassification.
5. Internal keys prefixed with `_` (`_tools`, `_ctx`, `_verb`) are stripped before sending to the frontend.
6. On terminal RULE success, the backend emits an `event` message `{type:"event", event:"views:refresh", payload:{table_name,...}}`; `ChatInterface` re-dispatches it as a `window` `CustomEvent` so the Sidebar refetches views.

Legacy `{"type":"run_rule","rule_code":"..."}` is still accepted for backwards compatibility.

---

## 4. Major Data Flows

### Flow A — CRUD (synchronous)

`Page onMount → fetch GET /{entity} → asyncpg pool → threat.v* view or base table → JSON → Svelte render`. Writes go through Pydantic validation → parameterized INSERT / UPDATE / DELETE. The `active_models` table scopes model-mode list endpoints implicitly via the `v*` views.

### Flow B — Rule execution (RULE verb, WebSocket)

```
ChatInput → ChatInterface builds envelope (verb=GENERIC, nextAgent=model.LanguageCapo)
  → /ws → PitbossSupervisor.process_envelope
  → LanguageCapo classifies verb (RULE) + fast-path "RUN <CODE>"
  → WorkflowEngine walks: model.Capo → verifyRequest → ruleToSQL → verifySQL → tool.executeSQL
  → SqlPitbossTool (OpenAI GPT-4o) → SQL
  → DataTableTool (DROP/CREATE VIEW) → RegisterViewTool (UPSERT views_registry)
  → each step emits a response envelope; decision=no suspends for HITL
  → terminal: emit views:refresh event + make_success
  → ChatInterface dispatches window 'views:refresh' → Sidebar refetches
```

### Flow C — Content extraction (CONTENT verb)

`Capo → verifyRequest → requestToExtractEntities → verifyUpsert → tool.executeSQL (ExecuteUpsertTool → CALL upsert_pattern_factory_entities(jsonb))`. Inserts orgs / guests / patterns / posts and junction rows.

### Flow D — Risk model generation (GENERATE verb, from a card)

`GENERATE <card_url>` → `agent_verify_request_generate` validates the URL matches `/cards/{id}/story` → `requestToExtractRiskModel` (LLM extracts threats / vulns / CMs / assets from card markdown) → `verifyUpsertRiskModel` → `ExecuteRiskModelUpsertTool` → `CALL threat.upsert_risk_model(jsonb)`. This is how a story card drives the threat model.

### Flow E — Big Picture dashboard

`/bigpicture onMount → fetch /query/THRIM → threat.threat_impact view (filtered by active_models) → top 5 threats → Google Charts ColumnChart`. Note: the page fetches `THRIM` (a view name) but the analytical view defined in `20260204-var.sql` is `threat.threat_impact` — `THRIM` must be registered in `views_registry` for `/query/THRIM` to resolve.

### Flow F — Mitigation level auto-computation

`INSERT / UPDATE on threats or countermeasure_threat or countermeasures.implemented / disabled → trigger → threat.compute_mitigation_level(id) → reads threat.threat_impact residual_risk_pct → UPDATE threats.mitigation_level`. Transparent to API / frontend.

---

## 5. Core Call Chains

### Rule → SQL → execute (the spine of the product)

```
api.websocket_endpoint
  └─ PitbossSupervisor.process_envelope
       ├─ ContextBuilder.reload_if_changed        # YAML hot-reload
       ├─ MessageEnvelope.from_dict               # validate verb
       ├─ call_agent("model.LanguageCapo")        # classify verb
       ├─ self._get_rule_from_yaml(rule_code)     # populate rule_logic
       └─ while loop:
            call_agent(current_agent, verb, message_body)
            WorkflowEngine.get_next_agent(verb, current_agent, decision)
            _send_envelope(make_response(...))    # frontend sees each step
            if decision==NO: return (HITL)
            if terminal: _send_event("views:refresh") + make_success
            else: current_agent = next_agent
```

Agent → tool wiring: agents read `message_body['_tools']` (`ToolRegistry`) and `message_body['_ctx']` (`ContextBuilder`). The `tool.executeSQL` agent node calls `ToolRegistry.execute("data_table", ...)` and `execute("register_view", ...)`.

### Model activation

```
models/+page.svelte row click → handleActivate
  → POST /models/{id}/activate   (api.activate_model → upsert active_models)
  → modeStore.setActiveModel(id, name)   # updates header + localStorage
  → goto('/bigpicture')
```

### Mode switch

```
Header.switchMode → modeStore.switchMode('model')
  → fetch /active-model → fetch /models/{id} → set store
  → goto('/models')
Sidebar subscribes to modeStore → fetchViews(mode) → GET /views?mode=
```

---

## 6. Potential Technical Debt

1. **Monolithic `api.py` (1468 lines).** All CRUD for 8 entities + WebSocket + generic query in one file. No router splitting, no service / repository layer. Hard to test, hard to navigate. Threat `PUT` uses a hand-rolled dynamic query builder while every other entity uses `COALESCE` patching — inconsistent.

2. **Hardcoded `CURRENT_USER_ID` stub** (`api.py:844`). No real auth / session. `activate_model` and `active-model` operate on a single fake user. The `threat_impact` view also uses `LIMIT 1` from `active_models`, so multi-user concurrency is unsafe.

3. **`allow_origins=["*"]` + credentials.** CORS is fully open in a credentialed config — fine for local dev, a security hole for any deployed environment. WebSocket URL and API base are hardcoded to `localhost:8000` / `ws://localhost:8000/ws` across the frontend (no env var).

4. **Frontend uses `window.location.href` for navigation.** Index pages navigate via `window.location.href = '/threats/'+id` instead of SvelteKit's `goto()`, causing full page reloads and losing SPA benefits. Inconsistent with `Header` / `models` which do use `goto`.

5. **Pre-existing TypeScript errors.** `svelte-check` reports errors in `SingleSelect` (`SelectItem` export), `assets/+page.svelte` `onMount` return type, and `ChatInterface` (`envelopeData` possibly undefined). The codebase ships with known type errors.

6. **Protocol drift between docs and code.** `workflow.py` defines a `CARD` verb branch in `get_hitl_next_agent` that is not in the RULE / CONTENT / GENERATE workflow maps — partial / dead branching logic. `Verb.CARD` exists in the enum but has no workflow tree.

7. **View name mismatch risk.** `/bigpicture` fetches `/query/THRIM` but the analytical view is `threat.threat_impact`. `THRIM` must exist as a `views_registry` row or the page silently fails. Coupling between page code and registry data is implicit.

8. **`threat_impact` view depends on `active_models`.** Analytical views silently filter by `SELECT model_id FROM public.active_models LIMIT 1` — a global side effect that makes queries non-deterministic across users and hard to test in isolation.

9. **LLM-generated SQL + open generic `/query/{table}`.** The `data_table` tool creates arbitrary views from LLM-generated SQL; combined with the open generic reader, the blast radius of a bad rule is large. `register_rule` references in `WARP.md` are stale (the rules table was dropped; `views_registry` is the single source).

10. **Debug `print()` statements in `context_builder.py`.** Production code logs to stdout via `print` alongside `logger` — noisy, not configurable.

11. **No test infrastructure wired in.** `package.json` has no `test` script; loose `test_*.py` files sit at the repo root with no pytest config or CI hook. `WARP.md` says "Currently minimal test setup."

12. **Tailwind remnants.** Project rules state Tailwind was removed, yet `package.json` still lists `tailwind-merge`, `tailwind-variants`, `tw-animate-css`, `shadcn-svelte`, `bits-ui`, `flowbite-svelte` — dependency cleanup is incomplete and conflicts with the "no Tailwind" rule.

13. **`mitigation_level` dual source of truth.** The column is `INTEGER NOT NULL` on `threats` and is also computed by `threat.compute_mitigation_level`. The trigger keeps them in sync, but direct API writes (`ThreatUpdate.mitigation_level`) can still override the computed value, creating drift. Consider making the column a generated column or dropping it from the update payload.

14. **Hardcoded `model_id: 1` defaults.** `ThreatCreate`, `AssetCreate`, etc. default `model_id=1` instead of deriving from `active_models`, so new entities can be silently attached to the wrong model.

---

## 7. Engineering Constraints for Future Refactoring

These constraints come from `WARP.md`, the persisted project rules, and observable conventions. They MUST be followed.

### 7.1 UI / Styling

- **No Tailwind CSS.** Do not reintroduce Tailwind. The remaining Tailwind-adjacent deps (`tailwind-merge`, `tailwind-variants`, `tw-animate-css`, `shadcn-svelte`, `bits-ui`, `flowbite-svelte`) should be removed, not extended.
- **Canonical CSS only: no inline styles.** All layout and spacing must use reusable utility classes from `main.css`. Inline `style=` attributes are forbidden except for dynamic values (e.g., computed `transform` for positioning). Never use page-scoped or component-scoped CSS for static styles. Reusable layout components (`EntityDetailLayout`, `CheckboxField`, `SingleSelect`) enforce this constraint. When adding new styles, extend the canonical set (e.g., `.error-margin`, `.section-spacing`, `.flex-row`, `.external-link`, `.help-text`) rather than creating ad-hoc inline rules.
- **Button class taxonomy:** `big-green-button` (add), `big-blue-button` (save / edit), `big-orange-button` (cancel), `big-red-button` (delete). Do not invent new button styles.
- **Consistent entity page pattern:**
  - Index — list + right-aligned add button + pencil / trash icons; row click = view, icon click = edit.
  - View — `heading heading-1` title + `heading heading-3` card + green EDIT button on the right.
  - Edit — form page; buttons bottom-right (`Cancel` / `Save`, or `Cancel` / `Edit Story` / `Save` for entities with Markdown stories).
  - No breadcrumbs / return buttons — the sidebar is the navigation.
- **Add-entity modal:** only name + description; buttons `Cancel` / `Save` (not `Create`). Details are added in the edit form.
- **CSV export** button / icon next to the search box on list pages.
- **Search box:** no blue focus border. Checkbox borders `#ccc`.
- **Pencil icon:** no blue background. Delete icon: red minus `-` (not red `X`) for sizing parity with the blue `+`.
- **Active model row:** pale green background. External entity links: superscript `↗` via `vertical-align: super`, opens in a new tab.

### 7.2 Navigation / Mode System

- **3+3 sidebar paradigm:** Explore = Patterns / Stories / Paths; Model = Models / Threats / Assets. Other pages (vulnerabilities, countermeasures, bigpicture) stay in the project but are not in the nav.
- Mode state lives in `modeStore` (localStorage) + backend `active_models`. Switching to Model mode fetches `/active-model`. Sidebar fetches `/views?mode=` and refreshes on the `views:refresh` window event.
- **Use SvelteKit `goto()` for navigation**, not `window.location.href`.

### 7.3 Backend / API

- asyncpg pool pattern (`get_pg_pool()` + `async with pool.acquire()`). **Parameterized queries only** — never interpolate user input. The `/query/{table}` sanitizer (`replace("_","").isalnum()` + quoted identifier) is the only sanctioned dynamic SQL.
- Pydantic `Create` / `Update` models per entity; `Update` uses all-optional fields with `COALESCE` patching (threats are the exception and should be normalized).
- Response shape conventions: CRUD returns row dicts; errors raise `HTTPException`; deletes return `{"status":"ok","deleted_id":...}`.
- `views_registry` is the single source for generated views (the old `rules` table is gone). Upsert by `table_name` (the YAML `rule_code`). Set `mode` (`'explore'` | `'model'`) when registering new views.

### 7.4 Pitboss / Message Protocol

- **Do not break Message Protocol v1.1.** The frontend must not modify `nextAgent`; it echoes it back. The frontend echoes `messageBody` and may only add `raw_text`. HITL resume keeps the SAME `verb` and SAME `nextAgent`.
- Internal DI keys (`_tools`, `_ctx`, `_verb`) are backend-only and must be stripped (`k.startswith('_')`) before any envelope reaches the frontend.
- Workflow trees live in `workflow.py` (hardcoded). `get_hitl_next_agent` defines resume targets and must be updated when adding agents. The `CARD` verb branch in `get_hitl_next_agent` is currently inconsistent with the workflow maps — fix or remove when refactoring.
- YAML hot-reload is a feature: `ContextBuilder.reload_if_changed()` is called at the start of every `process_envelope`. Keep prompts split across `SYSTEM/DATA/RULES/CAPO/CONTENT.yaml`.
- LLM calls go through `asyncio.to_thread` (the OpenAI client is sync). Preserve the async boundary; do not block the event loop.

### 7.5 Database

- Two schemas: `public` (pattern-factory entities) and `threat` (risk model). Reference threat entities as `threat.<table>` in YAML DATA descriptions.
- Analytical views (`threat.threat_impact`, `vthreats`, `vassets`, `vvulnerabilities`, `vcountermeasures`) are model-scoped via `active_models`. Be aware of this global dependency when testing.
- `threats.mitigation_level` is now trigger-computed from `threat.compute_mitigation_level`. Do not write to it from the API unless you intend to override the computed value; ideally drop it from `ThreatUpdate`.
- Migrations are date-prefixed SQL files in `backend/db/`, each wrapped in `BEGIN/COMMIT`. **Create functions / triggers BEFORE the triggers that reference them.** Backfill with `COALESCE(..., 0)` for `NOT NULL` columns.
- `kind` in `patterns` must be exactly `'pattern'` or `'anti-pattern'` (hyphenated) to satisfy the check constraint.

### 7.6 Process

- Commit messages and PR descriptions must include `Co-Authored-By: Oz <oz-agent@warp.dev>`.
- Run `npm run check` (svelte-check) after frontend changes; address new errors you introduce (pre-existing ones are tracked in §6).
- Prefer feature branches named `feature-pat-<issue>-<slug>` (matches existing convention).

---

## Appendix — Quick Reference

### Run commands

```bash
# Frontend
npm install
npm run dev          # http://localhost:5173
npm run check        # svelte-check type checking
npm run build

# Backend
cd backend
pip install -r requirements.txt
uvicorn services.api:app --reload --host 0.0.0.0 --port 8000

# Database
psql postgresql://pattern_factory:314159@localhost:5432/pattern-factory
```

### Key environment variables (`.env`)

| Variable | Purpose |
|---|---|
| `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, `PGPASSWORD` | Postgres connection |
| `DATABASE_URL` | Full connection string |
| `OPENAI_API_KEY` | GPT-4o / gpt-4o-mini for Pitboss |
| `API_HOST`, `API_PORT` | FastAPI binding (default 0.0.0.0:8000) |
| `PITBOSS_STRATEGY` | `llm_supervised` (default) |
| `VITE_API_BASE` | API endpoint for frontend (default http://localhost:8000) |

### Critical files

| File | Why it matters |
|---|---|
| `backend/services/api.py` | All REST + WebSocket endpoints |
| `backend/pitboss/supervisor.py` | Envelope processing, workflow loop |
| `backend/pitboss/workflow.py` | Decision trees (RULE / CONTENT / GENERATE) |
| `backend/pitboss/envelope.py` | Message Protocol v1.1 definition |
| `backend/pitboss/context_builder.py` | YAML hot-reload + LLM context assembly |
| `prompts/rules/*.yaml` | SYSTEM / DATA / RULES / CAPO / CONTENT DSL |
| `backend/db/threat_schema.sql` | `threat` schema tables |
| `backend/db/20260204-var.sql` | Analytical views (`threat.threat_impact`) |
| `backend/db/20260701-mitigation-level-function.sql` | `mitigation_level` computation |
| `src/lib/modeStore.ts` | Mode + active model state (localStorage) |
| `src/lib/ChatInterface.svelte` | WebSocket client, HITL handling |
| `src/lib/Sidebar.svelte` | 3+3 nav + views section |
