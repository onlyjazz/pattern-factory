# PAT-194: Swagger/OpenAPI API Documentation

## Overview

Comprehensive Swagger/OpenAPI documentation has been implemented for all backend API endpoints in the Pattern Factory. This provides interactive documentation, improved discoverability, and enables automatic client generation.

## Access Points

### 1. **Interactive Swagger UI (Recommended)**
```
http://localhost:8000/docs
```
- Full interactive API explorer
- Try endpoints directly from the browser
- Schema visualization
- Request/response examples

### 2. **ReDoc (Alternative UI)**
```
http://localhost:8000/redoc
```
- Clean, reader-friendly documentation
- Better for reading-focused browsing
- Organized by tags
- No interactive testing (but cleaner layout)

### 3. **OpenAPI Schema (JSON)**
```
http://localhost:8000/openapi.json
```
- Raw OpenAPI 3.0 specification
- For client generation tools
- For integration with other API platforms
- For documentation build systems

## Endpoint Categories

The API is organized into 14 semantic tags for easy navigation:

### Health
- `GET /` - API health check and status

### Patterns
- `GET /patterns` - List all patterns
- `GET /patterns/search` - Search patterns
- `GET /patterns/{id}` - Get single pattern
- `POST /patterns` - Create pattern
- `PUT /patterns/{id}` - Update pattern
- `DELETE /patterns/{id}` - Delete pattern

### Episodes
- CRUD operations for podcast episodes

### Guests
- CRUD operations for podcast guests

### Organizations
- CRUD operations for organizations

### Posts
- CRUD operations for blog posts and content

### Threats
- CRUD operations for threat models
- `GET /threats` - List threats
- `POST /threats` - Create threat
- `GET /threats/{id}` - Get threat details
- `PUT /threats/{id}` - Update threat
- `DELETE /threats/{id}` - Delete threat

### Assets
- CRUD operations for threat model assets
- Similar structure to threats

### Vulnerabilities
- CRUD operations for vulnerabilities
- Similar structure to threats

### Countermeasures
- CRUD operations for security countermeasures
- `GET /countermeasures` - List countermeasures
- `POST /countermeasures` - Create countermeasure
- `GET /countermeasures/{id}` - Get countermeasure
- `PUT /countermeasures/{id}` - Update countermeasure
- `DELETE /countermeasures/{id}` - Delete countermeasure

### Views
- `GET /views?mode=explore&limit=200` - Get registered views filtered by mode

**Response Example:**
```json
[
  {
    "id": 1,
    "name": "List Organizations",
    "table_name": "LIST_ORGS",
    "mode": "explore",
    "created_at": "2026-01-15T10:30:00Z",
    "updated_at": "2026-01-20T14:15:00Z"
  }
]
```

### Query
- `GET /query/{table}?limit=200` - Execute universal query against any table/view

**Security Features:**
- Table name validation (alphanumeric + underscore only)
- SQL injection prevention via prepared statements
- Server-side LIMIT enforcement
- Detailed error messages for debugging

**Examples:**
```
GET /query/LIST_ORGS?limit=50
GET /query/patterns?limit=100
GET /query/THRIM?limit=200
```

### WebSocket
- `ws://localhost:8000/ws` - Real-time Pitboss communication

**Supports:**
- Message Protocol v1.1 (envelope-based, recommended)
- Legacy run_rule format (backwards compatible)
- Human-In-The-Loop (HITL) workflows
- Structured error handling

**Message Protocol v1.1:**

Request:
```json
{
  "type": "request",
  "version": "1.1",
  "session_id": "sess-...",
  "request_id": "req-...",
  "verb": "RULE" | "CONTENT" | "GENERIC",
  "nextAgent": "agent-name",
  "decision": "yes" | "no" | null,
  "confidence": 0.0-1.0,
  "reason": "explanation",
  "messageBody": { ... }
}
```

Response:
```json
{
  "type": "response",
  "version": "1.1",
  "session_id": "sess-...",
  "request_id": "req-...",
  "verb": "...",
  "nextAgent": "next-agent-name",
  "decision": "...",
  "confidence": 0.0-1.0,
  "returnCode": 0 | 1 | -1,
  "messageBody": { ... }
}
```

### System
- `POST /log?event=...&context={...}` - Record events to audit log

**Example:**
```
POST /log?event=pattern_created&context={"pattern_id": 42, "user": "admin"}
```

## Key Features

### 1. **Self-Documenting Code**
Each endpoint includes comprehensive docstrings with:
- Detailed description of functionality
- Parameter documentation with types and constraints
- Return value documentation
- Error codes and exceptions
- Usage examples
- Security notes where applicable

### 2. **Parameter Documentation**
All parameters are documented using FastAPI's Query helper:
- Type hints (str, int, bool, dict)
- Default values
- Constraints and validation
- Human-readable descriptions

### 3. **Request/Response Examples**
Documentation includes examples for:
- Typical successful requests
- Expected response format
- Common error scenarios

### 4. **OpenAPI Schema**
Auto-generated from docstrings:
- OpenAPI 3.0.0 compliant
- Includes all endpoints, parameters, responses
- Security schemes and CORS configuration
- Database connection information
- Contact and license metadata

### 5. **Error Documentation**
Each endpoint documents:
- HTTP status codes (200, 201, 400, 404, 422, etc.)
- Error response format
- Validation errors
- Authentication/authorization failures

## API Conventions

### Response Format
All endpoints return JSON:
```json
{
  "id": 123,
  "name": "Entity Name",
  "created_at": "2026-01-20T14:15:00Z",
  "updated_at": "2026-01-20T14:15:00Z"
}
```

### Error Response Format
```json
{
  "detail": "Human-readable error message explaining what went wrong"
}
```

### Pagination
Most list endpoints support:
- `limit`: Maximum number of results (default: 200, max: varies by endpoint)

### Filtering
View-specific filtering:
- `mode`: 'explore' or 'model' (on `/views` endpoint)
- Search endpoints support `q` parameter for full-text search

## Integration Guide

### Using with Tools

**Generate TypeScript client:**
```bash
npx openapi-generator-cli generate -i http://localhost:8000/openapi.json -g typescript-fetch -o ./generated-client
```

**Generate Python client:**
```bash
pip install openapi-python-client
openapi-python-client generate --url http://localhost:8000/openapi.json
```

**Generate Go client:**
```bash
go install github.com/deepmap/oapi-codegen/cmd/oapi-codegen@latest
oapi-codegen -package client http://localhost:8000/openapi.json > client.go
```

### Manual Integration

**Get available views:**
```javascript
const response = await fetch('http://localhost:8000/views?mode=explore');
const views = await response.json();
```

**Query a view:**
```javascript
const tableName = views[0].table_name; // e.g., "LIST_ORGS"
const data = await fetch(`http://localhost:8000/query/${tableName}?limit=50`);
const rows = await data.json();
```

## Development Notes

### Adding Documentation to New Endpoints

1. **Add docstring with triple quotes:**
```python
@app.get("/new-endpoint", tags=["Category"])
async def new_endpoint(param: str = Query(..., description="Parameter description")):
    """Endpoint summary.
    
    Detailed description of what this endpoint does.
    
    Args:
        param (str): Parameter description and constraints
    
    Returns:
        dict: Response object with fields: field1, field2
    
    Raises:
        404: If resource not found
    
    Example:
        GET /new-endpoint?param=value
        Returns: {"field1": "value1", "field2": "value2"}
    """
```

2. **Use Query helper for parameters:**
```python
from fastapi import Query

@app.get("/endpoint")
async def endpoint(
    search: str = Query("", description="Search term"),
    limit: int = Query(200, ge=1, le=1000, description="Max results"),
    mode: str = Query("explore", regex="^(explore|model)$", description="Filter mode")
):
```

3. **Include error documentation:**
```python
if not row:
    raise HTTPException(
        status_code=404,
        detail=f"Resource {id} not found"
    )
```

### Viewing in Development

Start the API server:
```bash
cd backend
uvicorn services.api:app --reload --host 0.0.0.0 --port 8000
```

Then visit:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

## OpenAPI Metadata

The API is configured with:
- **Title:** Pattern Factory API
- **Version:** 2.1.0
- **License:** MIT
- **Contact:** Pattern Factory Team (https://github.com/onlyjazz/pattern-factory)
- **Base URL:** http://localhost:8000

## Performance Considerations

- Swagger UI is lightweight and doesn't impact API performance
- Schema generation is cached and served from memory
- Each request generates fresh OpenAPI JSON (FastAPI default)
- For production, consider caching the schema or serving static documentation

## Security Notes

- Documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) are publicly accessible
- For production, consider restricting documentation access behind authentication
- No sensitive data is exposed in OpenAPI schema (only structure)
- SQL injection is prevented via parameter validation and prepared statements

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenAPI 3.0 Specification](https://spec.openapis.org/oas/v3.0.3)
- [Swagger UI](https://swagger.io/tools/swagger-ui/)
- [ReDoc](https://redoc.ly/)
