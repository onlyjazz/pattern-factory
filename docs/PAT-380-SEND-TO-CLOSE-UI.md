# PAT-380 Send to Close — UI Notes

This document describes the frontend surface added for the PAT-380 "Send to Close"
flow. All pages live in the Product workspace and talk to the existing FastAPI
contract; no new dependencies were added.

## New pages and flows

### Experiments

- `/experiments` — index table of outreach experiments with a quick-add modal
  (name, description, arm). Columns: Name, Arm, Email Header status, step count,
  product count, Created. Rows open the detail page; the pencil opens edit; the
  trash deletes.
- `/experiments/{id}` — read-only detail (definition, steps table, product
  membership).
- `/experiments/{id}/edit` — full editor: name, description, arm,
  email_header, email_header_status, an ordered steps editor
  (position/channel/content_id/content_rev), and a searchable product
  membership multi-select.

Shared components:

- `src/lib/ExperimentDetail.svelte` — view + edit body, built on
  `EntityDetailLayout`.
- `src/lib/ExperimentStepsEditor.svelte` — ordered channel steps; positions are
  renumbered on add/remove and normalized again on save.
- `src/lib/ProductMultiSelect.svelte` — searchable checkbox list used for
  experiment product membership and on the Start Experiment page.
- `src/lib/ExperimentQuickAdd.svelte` — create modal for the index page.

### Start Experiment

- `/products/start-experiment` — choose an experiment, checkbox-select products
  (pre-selected from the experiment's membership), then
  `POST /experiments/{id}/start`. The response counts are rendered as
  "Started: N succeeded, M failed" plus any other numeric counters returned.
  Reached from the **Start Experiment** button on the Products index.

## Close tracking columns

- Products index adds Close Send Date, Final Decision, Arm, Tier, and Valuation
  columns; the Product detail adds a display-only "Send to Close" section
  (close_send_date, close_sent, arm, tier, size). The deprecated Company field
  was removed from the Product detail.
- Orgs index replaces the "Name Before Acquisition" column with Close Send Date;
  the Org detail shows a display-only Close Send Date.
- People index adds a Close Mail Send Date column; the Person detail shows
  display-only Close Mail Send Date and Close Mail Sent.

## Conventions

- `src/lib/formatDate.ts` renders every UI date in long US format
  ("June 30, 2026"). Date-only strings are parsed from their components so they
  do not shift a day in western time zones.
- All styling uses classes from `src/main.css`; no page-scoped `<style>` blocks
  or static inline styles. New classes: `multi-select*`, `steps-editor*`.
- Experiment arm values (`social`, `risk-then-superiority`,
  `superiority-then-risk`) and email header statuses (`draft`, `approved`) come
  from `src/lib/experiments.ts` so select boxes match the DB check constraints.
