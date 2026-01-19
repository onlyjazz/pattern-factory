ALTER TABLE public.views_registry add column mode TEXT default 'explore';
UPDATE public.views_registry set mode = 'explore';
UPDATE public.views_registry set mode = 'model' where id = 25;
--
