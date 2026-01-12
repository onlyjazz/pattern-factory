--
-- Logical views for reporting
-- Pattern-Guest relationships
DROP VIEW IF EXISTS pattern_guests;
CREATE OR REPLACE VIEW pattern_guests AS
SELECT
    p.name AS pattern_name,
    p.kind,
    p.content_source,
    g.name AS guest_name,
    g.job_description
FROM patterns p
JOIN pattern_guest_link pgl ON p.id = pgl.pattern_id
JOIN guests g ON pgl.guest_id = g.id
WHERE p.deleted_at IS NULL AND g.deleted_at IS NULL;
insert into views_registry (name, table_name, sql) 
values ('Patterns from guests', 'pattern_guests', 'select * from pattern_guests');

-- Pattern-Org relationships
DROP VIEW IF EXISTS pattern_orgs;
CREATE OR REPLACE VIEW pattern_orgs AS
SELECT
    p.name AS pattern_name,
    p.kind,
    p.content_source,
    o.name AS org_name,
    o.stage
FROM patterns p
JOIN pattern_org_link pol ON p.id = pol.pattern_id
JOIN orgs o ON pol.org_id = o.id
WHERE p.deleted_at IS NULL AND o.deleted_at IS NULL;
insert into views_registry (name, table_name, sql) 
values ('Patterns in orgs', 'pattern_orgs', 'select * from pattern_orgs');

-- Pattern-Post relationships
DROP VIEW IF EXISTS pattern_posts;
CREATE OR REPLACE VIEW pattern_posts AS
SELECT
    p.name AS pattern_name,
    p.kind,
    p.content_source,
    po.name AS post_name,
    po.content_url
FROM patterns p
JOIN pattern_post_link ppl ON p.id = ppl.pattern_id
JOIN posts po ON ppl.post_id = po.id
WHERE p.deleted_at IS NULL AND po.deleted_at IS NULL;
insert into views_registry (name, table_name, sql) 
values ('Patterns in posts', 'pattern_posts', 'select * from pattern_posts');

DROP VIEW IF EXISTS "PIP";
CREATE OR REPLACE VIEW "PIP" AS
 SELECT 
    p.name,
    p.description,
    '<a href="' || po.content_url || '">'||po.name || '</a>' AS source,
    p.kind,
    p.created_at,
    p.updated_at
   FROM patterns p
     JOIN pattern_post_link ppl ON p.id = ppl.pattern_id
     JOIN posts po ON ppl.post_id = po.id
     ORDER BY p.name ASC;