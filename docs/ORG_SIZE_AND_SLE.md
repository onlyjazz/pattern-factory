# Org valuation (`orgs.size`) and the asset SLE recompute

This documents how an organization's valuation (`public.orgs.size`) is calculated
and when it is recalculated, and how a change propagates into asset SLE values
(`threat.assets.sle_value`) and the risk views.

Implemented in:
- `backend/db/20260924-pat-371-recompute-asset-sle-on-valuation-change.sql`
- `backend/db/20260924-pat-374-propagate-sle-into-risk-views.sql`

## Summary

`orgs.size` is the valuation basis for every asset of the organization's models.
It can be set explicitly (e.g. a post-IPO market cap from public sources) or derived
from a rule of thumb. The current rule is:

- **Explicit valuation wins** when the write supplies `size`.
- Otherwise, `size` is **derived from `estimated_annual_sales` and `funding`**.
- A change to `size` cascades to `threat.assets.sle_value`, which feeds the
  threat views (`threat.threat_impact`, `THRIM`, `ENTERPRISE_RISK_TOP_5_SLE`).

> Caveat: by design a derived recalculation **overwrites** a previously pinned
> valuation when sales/funding change and `size` is not supplied. See
> "Protecting a pinned valuation" below.

## The default calculation

```
size = GREATEST(5 × estimated_annual_sales, 10 × funding)
tier = 1 if size >  $500,000,000   (Enterprise)
       2 if size >= $50,000,000    (Mid-Market)
       3 otherwise                 (Startup)
```

Functions:
- `public.compute_org_size_and_tier(sales, funding)` → returns `(computed_size, computed_tier)`
- `public.tier_for_size(size)` → tier from the thresholds above

## Triggers on `public.orgs`

| Trigger | Timing | Function | Purpose |
|---|---|---|---|
| `trg_compute_size` | `BEFORE INSERT` (row) | `update_org_size_and_tier()` | Always runs the default calculation on insert |
| `trg_org_size_a_explicit` | `BEFORE UPDATE OF size` (row) | `mark_org_size_explicit_on_update()` | Marks that the statement supplied `size`; derives `tier` from it |
| `trg_org_size_b_derive` | `BEFORE UPDATE` (row) | `derive_org_size_on_update()` | Applies the precedence rules below (runs on every update) |
| `trg_org_size_z_clear` | `AFTER UPDATE` (statement) | `clear_org_size_explicit_flag()` | Clears the explicit-size flag |
| `trg_recompute_asset_sle` | `AFTER UPDATE` (row) | `recompute_asset_sle_on_org_size_change()` | If `size` changed, recomputes the org's asset SLE values |

## Size/tier decision on UPDATE

| What the UPDATE does | Result for `size` |
|---|---|
| Supplies `size` (it appears in the SET list) | **Explicit wins** — kept as-is, even if equal to the current value. `tier` is derived from it. |
| Does not supply `size`, and `estimated_annual_sales` or `funding` changed | **Reset to the default calculation** |
| Does not supply `size`, and sales/funding unchanged | `size` kept; only `tier` re-derived from the existing `size` |

Notes:
- The reset keys on the value actually **changing**: `SET funding = funding` (no-op)
  does not reset; `SET funding = funding + 1` does.
- "Supplies `size`" is detected from the UPDATE **target list**, not from the value,
  so a form that round-trips an unchanged valuation still protects it.

### Explicit-size flag mechanics

`a_explicit` sets the transaction-local setting `pattern_factory.org_size_explicit`
when `size` is in the target list; `b_derive` reads and clears it. Because
PostgreSQL fires same-event triggers in alphabetical order, `trg_org_size_a_explicit`
runs before `trg_org_size_b_derive`. `trg_org_size_z_clear` clears any leftover flag
after the statement.

## INSERT behavior (known gap)

`trg_compute_size` always derives `size` on INSERT, so an explicitly supplied
valuation on INSERT is currently ignored. Extending the same precedence to INSERT
is an open follow-up.

## Downstream: asset SLE

When `size` changes, `trg_recompute_asset_sle` calls
`threat.recompute_asset_sle_values(org_id)`, which sets, for every model owned by
that organization and every taxonomy asset:

```
threat.assets.sle_value = orgs.size × threat.asset_valuation.valuation_percentage / 100
```

Asset valuation shares (`threat.asset_valuation`) come from
`backend/db/taxonomy-assets-v3.json` and sum to 100%:

| Tag | Asset | Share |
|---|---|---|
| A1 | Product / Clinical IP | 20% |
| A2 | Regulatory / Market Authorization | 15% |
| A3 | Revenue / Customer Franchise | 20% |
| A4 | Clinical / Patient Data | 10% |
| A5 | Brand / Trust | 10% |
| A6 | Operations / Service Delivery | 5% |
| A7 | Safety | 15% |
| A8 | Strategic / Enterprise Value | 5% |

The risk views then expose the quantitative threat model's figures:

- `gross_sle` — assets at risk = Σ (asset `sle_value` × damage %)
- `sle` = assets at risk × threat probability / 100
- `sle_after_mitigation` = `sle` × residual multiplier (floored at 5%)

See `docs/VALIDATION_RESIDUAL_RISK_CALCULATIONS.md` for the residual/mitigation math.

## API behavior (`PUT /orgs/{id}`)

`backend/services/api.py` adds `size` to the SET clause **only when the caller
supplies it** (`patch.size is not None`). Consequences:

- Caller sends a valuation → it is pinned (explicit wins).
- Caller omits the valuation and changes sales/funding → **size resets to the default calculation**.
- Caller omits the valuation and leaves sales/funding alone → size unchanged.

## Worked example

For an org with `size = 3,100,000,000`, `estimated_annual_sales = 50,511,000`,
`funding = 156,985,000`:

```
-- Resets the valuation (size not supplied; funding changed)
UPDATE public.orgs SET funding = funding + 1 WHERE id = 177;
--   size: 3,100,000,000 -> 1,569,850,010   (10 x funding dominates)
--   A1 sle_value:        620,000,000 -> 313,970,002
```

```
-- Protects the valuation (size supplied, even unchanged)
UPDATE public.orgs SET funding = funding + 1, size = size WHERE id = 177;
--   size: 3,100,000,000 (unchanged); A1 sle_value unchanged
```

## Guidance for the org CRUD UI

Include `size` in the update payload **whenever the org has a pinned valuation**
(i.e. always send the valuation field, even if the user did not touch it).
Otherwise a save that changes sales/funding will silently overwrite the valuation
with the rule of thumb.

If a sticky valuation is wanted (e.g. fall back to the rule of thumb only when
`size` is NULL/0, or only on an explicit "recalculate" action), that is a small
trigger change to `derive_org_size_on_update()`.

## Inspecting the behavior

```bash
# Triggers on public.orgs
psql -d pattern-factory -c "\d public.orgs"

# Live trigger/function definitions
psql -d pattern-factory -c "SELECT tgname, pg_get_triggerdef(t.oid)
  FROM pg_trigger t
  JOIN pg_class c ON c.oid = t.tgrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public' AND c.relname = 'orgs' AND NOT t.tgisinternal
  ORDER BY tgname;"

# Recompute on demand for one org (or all orgs with no argument)
psql -d pattern-factory -c "SELECT threat.recompute_asset_sle_values(177);"
psql -d pattern-factory -c "SELECT threat.recompute_asset_sle_values();"
```

Always verify against the live database with `psql`; migrations are historical.
