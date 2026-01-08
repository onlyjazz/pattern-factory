-- paths table yaml field contains mermaid flowchart in string format with nodes and edges and optionality attribute
-- optionality attribute, for example: 
-- optionality: 
--   collapses: true
--   reason: "Installed base exists"
create table paths (
    id serial primary key,
    name text not null,
    yaml text,
    created_at timestamp with time zone default current_timestamp,
    updated_at timestamp with time zone default current_timestamp
)
