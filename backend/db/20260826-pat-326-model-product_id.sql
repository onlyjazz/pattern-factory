DROP VIEW public.model_product;
create OR replace view public.model_product AS
select m.ctid, m.created_at as model_created_date, 
m.id as model_id,p.id as product_id, m.name,p.submission_number, p.org_id as company_id,
p.panel, p.intended_use, p.indications_for_use,
p.company, p.device, substring(m.name,1, strpos(m.name,'+PRODUCT')-1) as product_name,
p.device_description, p.superiority 
from 
threat.models m, public.products p
where  p.device = substring(m.name,1, strpos(m.name,'+PRODUCT')-1) AND
m.created_at >= now()::date
ORDER by submission_number;
SELECT * from model_product
--
-- Add reference to the product that generated the threat set
ALTER TABLE threat.models  ADD COLUMN product_id integer default null references public.products(id);

-- Update the new models.product_id col
UPDATE threat.models m
SET product_id = v.product_id
FROM public.model_product v
WHERE m.id = v.model_id;

-- Update the products.process_flag if the product inserted a model
-- Default processing false
UPDATE public.products SET process_flag = 'f';
UPDATE public.products p SET process_flag = 't' 
WHERE p.id IN (SELECT product_id FROM threat.models);

-- Constrain
ALTER TABLE threat.models
ADD CONSTRAINT models_product_id_unique
UNIQUE (product_id);