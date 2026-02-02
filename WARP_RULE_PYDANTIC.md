# WARP Rule: Backend Pydantic Model Updates

When updating backend API to support new database columns/fields, ALWAYS update both:

1. **Database schema** (SQL migrations)
2. **Pydantic models** in `backend/services/api.py` (AssetCreate, AssetUpdate, ThreatCreate, ThreatUpdate, VulnerabilityCreate, VulnerabilityUpdate, CountermeasureCreate, CountermeasureUpdate, etc.)

The Pydantic models MUST have fields that match the database columns being queried and returned in the API responses. Failure to do so will result in `UndefinedColumnError` exceptions.

## Pattern

For any new database field, ensure:
- Add the field to the corresponding Pydantic `Create` class with appropriate default
- Add the field to the corresponding Pydantic `Update` class with optional type
- Update all API endpoints that return the entity to include the new field in SELECT statements
- Test that the field is properly persisted and retrieved

Example:
```python
# ❌ WRONG - missing fields in Pydantic model
class AssetCreate(BaseModel):
    name: str
    description: str

# ✅ CORRECT - all fields in Pydantic model
class AssetCreate(BaseModel):
    name: str
    description: str
    fixed_value: float = 0
    fixed_value_period: int = 12
    recurring_value: float = 0
    include_fixed_value: bool = True
    include_recurring_value: bool = True
```
