# PAT-380: Send to Close — Implementation Notes

Backend implementation for handing selected products (and their orgs/people) to
Close CRM from a reusable experiment template.

## Components

- `backend/services/close_service.py` — async Close CRM client (httpx).
- `backend/services/sanity_service.py` — **stubbed**, read-only Sanity seam (no network).
- `backend/services/api.py` — experiments CRUD + activation endpoints; `close_*`
  columns added to orgs / products / people.
- `backend/db/20261009-pat-380-send-to-close.sql` — schema (contract, already applied).
- `prompts/rules/CLOSE.yaml` — Close config (contract).

## Close mapping

`close_service` loads `prompts/rules/CLOSE.yaml` at runtime (same pattern as the
SEARCH.yaml loader in `backend/pitboss/competitors.py`). The API `base_url`,
`api_key_env` (`CLOSE_API_KEY`) and timeout come from the YAML — no endpoint
base URL is hard-coded. Close custom-field ids are read from
`CLOSE.company_field_map` and are never hard-coded in Python.

`build_company_custom_field_payload(experiment, product, org)` walks
`company_field_map`, whose keys are Pattern Factory `table.column` names
(`experiment.name`, `products.device`, `products.competitors`,
`products.superiority`, `products.date_of_final_decision`,
`products.intended_use`, `orgs.estimated_annual_sales`, `orgs.size`,
`orgs.arm`), and returns a `{field_id: value}` payload for the Close lead
`custom` object. Empty/None values are skipped and datetimes are ISO-8601
serialized. `CLOSE.unmapped_fields` (`products.product_count`, `products.sle`)
is declared but intentionally not sent.

Public functions:

- `find_or_create_company(name, custom_fields)` — searches Close
  (`GET /lead/?query=name:"..."`) and only creates via `POST /lead/` when no
  lead matches; returns the Close lead id.
- `create_contact(company_id, person)` — dedupes via Close search (by email,
  else name) and creates via `POST /contact/` linked to `lead_id`; returns the
  Close contact id.
- `create_smart_view(name, query)` — creates a Close saved search
  (`POST /saved_search/`) for the experiment; returns its id.
- `build_experiment_smart_view_query(name)` — builds the saved-search query
  scoped to the `experiment.name` custom field id.

HTTP errors raise `CloseAPIError`; missing config/key raises `CloseConfigError`.
The `Authorization` header (API key) is never logged.

## Sanity stub contract

Sanity is **not integrated yet**. `sanity_service` is a deterministic, read-only
seam:

- `get_brief(content_id)` returns `{_id, _rev, _type, title, status, approved,
  source}` derived only from `content_id`, or `None` for a falsy id. `_rev` is a
  stable `stub-<sha1[:12]>` hash.
- A content id starting with `"draft"` (case-insensitive) yields
  `status == "draft"` / `approved == False`; anything else yields approved.
- `is_approved(brief)` is True only for an approved brief.

Env vars `SANITY_PROJECT_ID`, `SANITY_DATASET`, `SANITY_API_TOKEN` are read for
forward compatibility only; no request is made and the token is never logged.

## Activation flow (`POST /experiments/{id}/start`)

Body: `StartExperimentRequest { product_ids }`. Returns
`{experiment_id, smart_view_id, smart_view_error, success_count, failure_count,
results[]}`.

1. 404 if the experiment is missing; 400 if `product_ids` is empty, the
   experiment has no steps, or a requested product does not exist.
2. Create the Close smart view **once** for the experiment (failures are
   recorded in `smart_view_error` and do not abort the run).
3. Per product (one `experiment_run`, in its own DB transaction):
   - Pin `model_id` from `threat.models.product_id` (latest model for the
     product).
   - Pin steps from Sanity briefs; a step whose brief is not approved is
     refused (counted in `steps_refused`, not inserted).
   - Resolve the product's org to a Close company (custom fields from
     `CLOSE.yaml`), then the org's people to Close contacts (deduped).
   - Insert `experiment_run_step`, `experiment_run_target` and
     `experiment_run_send` rows (`state = 'pending'`).
   - Stamp `products.close_sent` / `close_send_date`,
     `orgs.close_sent` / `close_send_date`, and
     `people.close_mail_sent` / `close_mail_send_date`.
   - A failure rolls back that product's DB writes and is reported in
     `results[].error`; other products continue.
4. Log `CLOSE_SEND_COMPLETE` via `log_event`.

`GET /experiments/{id}/runs` returns each run with nested steps, targets, and
per-step send state.

## Tests

Hermetic suite (no DB/OpenAI/network), using the fake asyncpg pool in
`backend/tests/conftest.py` and patched Close/Sanity calls:

- `backend/tests/test_close_fields_api.py` — `close_*` round-trip on orgs,
  products, people.
- `backend/tests/test_experiments_api.py` — experiments CRUD, activation
  (success/404/400/refusal), runs.
- `backend/tests/test_close_service.py` — Close field mapping + Sanity stub.

Run from the repo root: `python -m pytest -q`.
