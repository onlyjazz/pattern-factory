delete  from orgs where description is null;
delete from products where submission_number like 'UNK%';
--
create or replace view companies_with_products as       
	  SELECT 
          o.id, o.name, s.name AS status, o.estimated_annual_sales, o.arm,o.size,
          COUNT(p.id) AS product_count
      FROM 
          public.orgs o
      JOIN public.products p ON o.id = p.org_id
      JOIN public.statuses s ON o.status_id = s.id
      GROUP BY 
          o.id, o.name, s.name,o.estimated_annual_sales, o.arm,o.size;

create or replace view companies_without_products as
    SELECT o.id, o.name
    FROM public.orgs o
    LEFT JOIN public.products p ON o.id = p.org_id
    WHERE p.id IS NULL
    ORDER BY o.name;

delete from orgs where id in (select id from companies_without_products);

create or replace view companies_without_people AS
    SELECT o.id, o.name
    FROM public.orgs o
    WHERE NOT EXISTS (
        SELECT * FROM public.people p WHERE p.org_id = o.id
    )
    ORDER BY o.name;
