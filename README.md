# Pattern Factory

Pattern Factory is an application with a Svelte 5 front-end and Python FastAPI backend using Postgresql 17
and a system of AI agents and tools to derive the patterns and antipatterns from the content.

The supervisor of the system of agents and tools is called PitBoss and is stored in the backend/pitboss directory.
The API services are stored in the backend/services directory in the api.py file.
The api.py file implements CRUD queries for the patterns table and a general purpose api to select from a table.

The database schema is stored in the backend/db directory.
The frontend is stored in the src directory.

The data model looks like this

| categories           | table of categories 
| episodes             | table of episodes
| guests               | table of guests
| orgs                 | table of orgs
| patterns             | table of patterns
| posts                | table of posts
| rules                | table of rules
| pattern_episode_link | table of pattern_episode_link
| pattern_guest_link   | table of pattern_guest_link
| pattern_org_link     | table of pattern_org_link
| pattern_post_link    | table of pattern_post_link
| pattern_registry     | table of pattern_registry
| system_log           | table of system_log 
| views_registry       | table of views_registry

The prompts/rules directory contains pattern-factory.yaml which is the main prompt for the system
and contains the rules for building various logical views of the data. The idea is to create a system
that can build itself - with natural language rules for building materialized views of the data.

The views are recorded in the views_registry table and exposed in the left-hand panel of the UI 
underneath the Patterns link. Each link to a view (for example PATTERN_IN_EPISODE) renders a DataTable (using Datatable.js)
that shows the results of the view inside the application-content-area div area of the UI replacing any previous content.
The sidebar links (patterns, views, etc.) enable the user to navigate in the content.

## CRUD for Patterns, Episodes, Guests, Orgs, Posts

Rev #1 implements CRUD for Patterns
The frontend/src/routes/patterns directory contains the patterns page and a patterns-add-edit.html tamplate.
The patterns page shows a table of patterns and provides a green "Add Pattern" link to add a new pattern
and edit/delete functions using the three dot form.

Rev #3 will implement CRUD for Episodes, Guests, Orgs, Posts

## Agent Chat area

Rev #2 implements an agent chat area that allows the user to interact with the system of agents and tools.
The first usage of the agent chat area is to allow the user to invoke a workflow with a language agent that parses the natural language DSL rules in the pattern-factory.yaml file, translates to a valid SQL query, and executes it against the database creating a materialized view (a Postgres table) and registering it in the views_registry table.

The agent chat area will enable the user to execute a single rule or several rules or all the rules with a single command -
run rule, run rules, run all rules.

## Web sockets
The agent chat area will use web sockets to enable the user to see the progress of the agent as it executes the rules
and communicate with the user in real time - providing HITL (human in the loop) capabilities.
The Pitboss backend will use web sockets to communicate with the user in real time - providing HITL (human in the loop) capabilities.

## Content source
The source of the content is a substack newsletter and videos from my Life Sciences Today Podcast that were
transcribed into text summaries using Granola.  
Additional agents will read the content and extract patterns and antipatterns and call the API to insert/update/delete the patterns, episodes, guests, orgs, posts in the database.

## Rev 0.1
Key tasks for this Release:
- Run the API Server DONE
- Create database schema DONE
- Create test data DONE
- API for patterns DONE
- Configure for Postgresql DONE
- Run the Frontend - render list of patterns and enable CRUD for patterns - In progress
