-- ============================================
-- PAT-380: Send to Close — Experiments & Close CRM
-- ============================================
-- Adds Close CRM send-tracking columns to the product-area tables and the
-- Experiment / Experiment Run tables used to push products to Close.
--
-- Snake_case is the repo convention; the PAT-380 spec's camelCase fields
-- (productId, contentId, contentRev, ...) map to the snake_case columns here.

-- ---------------------------------------------------------------------------
-- Close send tracking on existing product-area tables
-- ---------------------------------------------------------------------------
ALTER TABLE public.orgs
    ADD COLUMN IF NOT EXISTS close_send_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS close_sent BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE public.products
    ADD COLUMN IF NOT EXISTS close_send_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS close_sent BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE public.people
    ADD COLUMN IF NOT EXISTS close_mail_send_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS close_mail_sent BOOLEAN NOT NULL DEFAULT false;

-- ---------------------------------------------------------------------------
-- experiment: reusable cross-channel outreach template
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.experiment (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    arm TEXT NOT NULL CHECK (arm IN ('social', 'risk-then-superiority', 'superiority-then-risk')),
    email_header TEXT,
    email_header_status TEXT NOT NULL DEFAULT 'draft' CHECK (email_header_status IN ('draft', 'approved')),
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);

-- experiment_step: ordered channels for the experiment (Sanity content pinned at activation)
CREATE TABLE IF NOT EXISTS public.experiment_step (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT NOT NULL REFERENCES public.experiment(id) ON DELETE CASCADE,
    position INT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('buffer', 'email')),
    content_id TEXT,
    content_rev TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    UNIQUE (experiment_id, position)
);

-- experiment_product: many-to-many membership authored at experiment creation
CREATE TABLE IF NOT EXISTS public.experiment_product (
    experiment_id BIGINT NOT NULL REFERENCES public.experiment(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (experiment_id, product_id)
);

-- ---------------------------------------------------------------------------
-- experiment_run: one row per product at activation (product + model pinned)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.experiment_run (
    id BIGSERIAL PRIMARY KEY,
    experiment_id BIGINT NOT NULL REFERENCES public.experiment(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    model_id BIGINT REFERENCES threat.models(id) ON DELETE SET NULL,
    email_header_sent BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- experiment_run_step: content pinned at activation
CREATE TABLE IF NOT EXISTS public.experiment_run_step (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES public.experiment_run(id) ON DELETE CASCADE,
    position INT NOT NULL,
    content_id TEXT,
    content_rev TEXT,
    created_at TIMESTAMP DEFAULT now(),
    UNIQUE (run_id, position)
);

-- experiment_run_target: Close company/contact resolved per run
CREATE TABLE IF NOT EXISTS public.experiment_run_target (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES public.experiment_run(id) ON DELETE CASCADE,
    person_id BIGINT REFERENCES public.people(id) ON DELETE SET NULL,
    company_id TEXT,
    contact_id TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- experiment_run_send: per-step hand-off state for each target
CREATE TABLE IF NOT EXISTS public.experiment_run_send (
    id BIGSERIAL PRIMARY KEY,
    target_id BIGINT NOT NULL REFERENCES public.experiment_run_target(id) ON DELETE CASCADE,
    position INT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'handedOff', 'rejected', 'failed')),
    external_id TEXT,
    handed_off_at TIMESTAMP,
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_experiment_step_experiment_id ON public.experiment_step(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_product_product_id ON public.experiment_product(product_id);
CREATE INDEX IF NOT EXISTS idx_experiment_run_experiment_id ON public.experiment_run(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_run_product_id ON public.experiment_run(product_id);
CREATE INDEX IF NOT EXISTS idx_experiment_run_step_run_id ON public.experiment_run_step(run_id);
CREATE INDEX IF NOT EXISTS idx_experiment_run_target_run_id ON public.experiment_run_target(run_id);
CREATE INDEX IF NOT EXISTS idx_experiment_run_target_person_id ON public.experiment_run_target(person_id);
CREATE INDEX IF NOT EXISTS idx_experiment_run_send_target_id ON public.experiment_run_send(target_id);

-- ---------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS update_experiment_updated_at ON public.experiment;
CREATE TRIGGER update_experiment_updated_at
BEFORE UPDATE ON public.experiment
FOR EACH ROW EXECUTE PROCEDURE public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_experiment_step_updated_at ON public.experiment_step;
CREATE TRIGGER update_experiment_step_updated_at
BEFORE UPDATE ON public.experiment_step
FOR EACH ROW EXECUTE PROCEDURE public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_experiment_run_updated_at ON public.experiment_run;
CREATE TRIGGER update_experiment_run_updated_at
BEFORE UPDATE ON public.experiment_run
FOR EACH ROW EXECUTE PROCEDURE public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_experiment_run_target_updated_at ON public.experiment_run_target;
CREATE TRIGGER update_experiment_run_target_updated_at
BEFORE UPDATE ON public.experiment_run_target
FOR EACH ROW EXECUTE PROCEDURE public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_experiment_run_send_updated_at ON public.experiment_run_send;
CREATE TRIGGER update_experiment_run_send_updated_at
BEFORE UPDATE ON public.experiment_run_send
FOR EACH ROW EXECUTE PROCEDURE public.update_updated_at_column();
