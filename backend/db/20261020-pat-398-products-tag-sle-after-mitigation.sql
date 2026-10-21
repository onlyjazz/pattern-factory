/*
 * PAT-398: product tag + SLE after mitigation.
 *
 * Adds two columns to public.products:
 *
 *   tag                   free-text label used to select tagged products for
 *                         an experiment
 *   sle_after_mitigation  the product's total exposure after mitigation
 *
 * and backfills sle_after_mitigation from public.product_sle_after_mitigation,
 * the logical view defined in
 * backend/db/20261016-pat-398-product-sle-after-mitigation-view.sql.
 *
 * The backfill joins the view on product_id, so the view migration must be
 * applied first (it is idempotent — CREATE OR REPLACE VIEW):
 *
 *   psql pattern-factory \
 *     -f backend/db/20261016-pat-398-product-sle-after-mitigation-view.sql
 *   psql pattern-factory \
 *     -f backend/db/20261020-pat-398-products-tag-sle-after-mitigation.sql
 *
 * The backfill is a one-time UPDATE, not a trigger: products.sle_after_mitigation
 * is a derived snapshot, so re-run this file (both statements are idempotent)
 * after the underlying model data changes.
 *
 * products.sle_after_mitigation is NUMERIC; the view returns BIGINT, which the
 * UPDATE widens implicitly.
 */

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS tag TEXT,
    ADD COLUMN IF NOT EXISTS sle_after_mitigation NUMERIC;

-- Backfill every product the view has a row for. The view's product_id is
-- threat.models.product_id, and models.product_id -> products.id is 1:1, so
-- each product takes its single model's rolled-up exposure. Products with no
-- model, or with no matching core-asset threats, keep NULL.
UPDATE public.products p
SET sle_after_mitigation = v.sle_after_mitigation
FROM public.product_sle_after_mitigation v
WHERE v.product_id = p.id;

COMMIT;
