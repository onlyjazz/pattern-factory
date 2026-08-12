# Pattern Factory v1.0 - First Production Release

**Release Date:** December 9, 2025

## Overview

Pattern Factory is a full-stack AI-driven application for extracting patterns and antipatterns from podcast transcripts and Substack content, storing them with linked relationships across episodes, guests, organizations, and posts.

## Major Features

### 1. RULE Flow
Convert natural language rules into SQL queries and create materialized views.

- **Entry:** "RUN <RULE_CODE>"
- **Pipeline:** LanguageCapo → Capo → verifyRequest → ruleToSQL → verifySQL → executeSQL
- **Output:** Materialized view with linked data
- **HITL:** SQL validation with human approval before execution

### 2. CONTENT Flow
Extract entities from web content and upsert to database with full validation.

- **Entry:** "extract <url>"
- **Pipeline:** LanguageCapo → Capo → verifyRequest → requestToExtractEntities → verifyUpsert → executeSQL
- **Output:** Entities (orgs, guests, posts, patterns) with relationships persisted to database
- **Validation:** Structural, referential, and safety checks before upsert

### 3. Agent Architecture
Modular, composable agent system with deterministic decision trees:

- **model.LanguageCapo:** Pre-workflow routing (RULE vs CONTENT)
- **model.Capo:** Message envelope validation
- **model.verifyRequest:** Semantic validation (RULE flow)
- **model.verifyRequest_content:** Extraction validation (CONTENT flow)
- **model.ruleToSQL:** LLM-based rule-to-SQL conversion
- **model.verifySQL:** SQL safety validation with HITL
- **model.requestToExtractEntities:** Web content extraction via LLM
- **model.verifyUpsert:** Entity payload validation
- **tool.executeSQL:** Dual-flow execution (views or upsert)

### 4. Message Protocol v1.1
Unified envelope for all frontend ↔ backend communication:

- Type: request | response | error
- Verb: RULE | CONTENT | GENERIC
- Decision: yes | no (for workflow branching)
- nextAgent: Name of next agent (for HITL and routing)
- returnCode: 0 (continue) | 1 (success) | -1 (error)

### 5. Human-In-The-Loop (HITL)
Workflow pauses for human review/approval at strategic points:

- SQL validation: User reviews and approves generated SQL
- Frontend shows `Next: <agent>` for user reference
- User responds and workflow resumes automatically

## Technology Stack

- **Frontend:** Svelte 5 + SvelteKit (TypeScript)
- **Backend:** Python FastAPI with async Postgres (asyncpg)
- **Database:** PostgreSQL 17
- **AI System:** OpenAI GPT-4o for natural language processing
- **Communication:** WebSocket for real-time updates
- **Message Protocol:** JSON envelopes with versioning

## Database Components

### Core Tables
- `patterns`: Pattern definitions (id, name, description, kind)
- `episodes`: Podcast episode metadata
- `guests`: Interview participants
- `orgs`: Organizations mentioned
- `posts`: Substack posts and content
- `pattern_*_link`: Junction tables for many-to-many relationships

### System Tables
- `views_registry`: Materialized view metadata (consolidated from rules table)
- `system_log`: Audit logging for all operations
- `Attendance`: Group class attendance tracking
- `patientPayments`: Patient payment history (physiotherapy clinic extension)

## Key Implementation Details

### Validation Pipeline (verifyUpsert)
- ✅ Structural validity (all required arrays present)
- ✅ Required fields (name, kind, etc.)
- ✅ Link table consistency (no orphan references)
- ✅ Safety validation (no SQL injection patterns)
- ✅ Semantic checks (URL/source consistency, timestamps)

### Tool Registry
- **sql_pitboss:** LLM-based rule-to-SQL conversion
- **data_table:** Creates materialized views (CREATE VIEW)
- **register_view:** Records view metadata in views_registry
- **execute_upsert:** Calls PostgreSQL `upsert_pattern_factory_entities` procedure

### Workflow Engine
Deterministic decision trees for RULE and CONTENT flows:

```
RULE:  Capo → verifyRequest → ruleToSQL → verifySQL → executeSQL
CONTENT: Capo → verifyRequest → requestToExtractEntities → verifyUpsert → executeSQL
```

## Testing Checklist

✅ RULE flow: Extract URL → Parse JSON → Validate structure → Execute procedure
✅ CONTENT flow: Natural language → SQL → Validate → Execute → View created
✅ HITL: User approves SQL → Workflow resumes → View created
✅ Entity validation: Rejects orphan links, missing fields
✅ Error handling: Graceful failures at each stage
✅ Async operations: All DB calls non-blocking

## Configuration

### Environment Variables (.env)
```
PGHOST=localhost
PGPORT=5432
PGUSER=pattern_factory
PGDATABASE=pattern-factory
PGPASSWORD=<password>

API_HOST=0.0.0.0
API_PORT=8000

OPENAI_API_KEY=<key>
VITE_API_BASE=http://localhost:8000
```

### YAML Configuration (pattern-factory.yaml)
- `CAPO`: Language classification prompt
- `RULES`: Rule definitions (rule_code, name, logic)
- `CONTENT`: Entity extraction rules (EXTRACT_CONTENT, VERIFY_UPSERT prompts)
- `DATA`: Schema description for LLM context

## Performance Characteristics

- **Async throughout:** All database operations non-blocking
- **LLM calls:** ~2-5 seconds for rule-to-SQL, ~3-8 seconds for entity extraction
- **Database upserts:** <100ms for typical payloads
- **WebSocket latency:** Real-time updates on all agent decisions

## Known Limitations

1. EXTRACT_CONTENT optimized for Substack content (HTML patterns)
2. Entity extraction requires valid OpenAI API key
3. Materialized views not indexed by default
4. No duplicate detection across extractions
5. No batch processing for multiple URLs

## Future Enhancements

- Add confidence scoring for extracted entities
- Implement duplicate detection across documents
- Support additional content sources (Twitter, Medium, etc.)
- Add batch processing for URL lists
- Implement audit logging for compliance
- Add result caching for repeated queries
- Support for custom LLM models

## Files & Documentation

- **docs/EXTRACT_CONTENT_IMPLEMENTATION.md**: Complete extraction flow design
- **docs/EXTRACT_CONTENT_QUICK_REFERENCE.md**: Quick reference for implementation
- **docs/UPSERT_FLOW.md**: Entity upsert procedure details
- **backend/pitboss/**: Agent implementations
- **backend/services/**: FastAPI service layer
- **prompts/rules/pattern-factory.yaml**: LLM prompts and schema

## Support & Maintenance

For issues or enhancements, refer to:
- Agent architecture: `backend/pitboss/agents.py`
- Workflow logic: `backend/pitboss/workflow.py`
- Message protocol: `backend/pitboss/envelope.py`
- Database procedures: PostgreSQL schema files

---

**Version:** 1.0.0  
**Release Date:** December 9, 2025  
**Status:** Production Ready
