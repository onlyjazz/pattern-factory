drop view "PIP" if EXISTS;
--
alter table guests drop column keywords;
alter table orgs drop column keywords;
alter table patterns drop column keywords;
alter table posts drop column keywords; 
--
alter table patterns drop column metadata;
alter table patterns drop column highlights;
--
