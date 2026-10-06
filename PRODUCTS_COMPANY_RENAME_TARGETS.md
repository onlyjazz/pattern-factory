# Products.company Rename Impact Analysis

## Status
Column renamed: `products.company` → `products.company_from_fda_import_deprecated`  
Index renamed: `idx_products_company` → `idx_products_company_from_fda_import_deprecated`  
DATA.yaml updated: ✅

## Files Requiring Updates

### 1. **Backend Python (Agent/Service Code)**

#### `backend/pitboss/competitors.py`
- **Lines affected**: 349, 382, 484, 514
- **Issue**: Reads and writes `product.get("company")` in agent flows
- **Code pattern**: 
  ```python
  company_name = (product.get("company") or "").strip()
  # and
  competitor.get("company")
  # and  
  product.get("company")
  ```
- **Fix**: This agent needs the column data from products table. Decision point: should use new column name OR source company from org relationship (org.name via products.org_id)

#### `backend/pitboss/feelgood.py`
- **Lines affected**: 98, 111, 126-127, 140, 281, 391
- **Issue**: SELECT queries and validation checks
- **Code pattern**:
  ```python
  SELECT id, submission_number, device, company, intended_use, ...
  if not result.get("company"):
      missing_fields.append("company")
  reason = f"Product {product_id} found: {result['device']} by {result['company']}"
  ```
- **Fix**: Update SELECT statement to use new column name OR fetch from org relationship

#### `backend/pitboss/profile.py`
- **Lines affected**: 458, 561, 707
- **Issue**: Reads company field from product dict
- **Code pattern**:
  ```python
  company = (product.get("company") or "").strip()
  ```
- **Fix**: Use new column name OR get from org relationship

#### `backend/scripts/load_products.py`
- **Lines affected**: 75, 90, 107, 136, 146
- **Issue**: CSV loader inserts into `company` column
- **Code pattern**:
  ```python
  company = row.get("Company", "").strip()
  INSERT ... company ...
  VALUES ... row["company"] ...
  ```
- **Fix**: Update INSERT to use `company_from_fda_import_deprecated` column instead

#### `backend/services/fda_devices_lookup.py`
- **Line affected**: 357
- **Issue**: Query references company field

#### `backend/services/fda_primary_source.py`
- **Line affected**: 267
- **Issue**: Query references company field

#### `backend/services/openfda_service.py`
- **Line affected**: 374
- **Issue**: Query references company field

#### `backend/services/basis_threats_service.py`
- **Line affected**: 548
- **Issue**: Query references company field

#### `backend/services/threat_selector_service.py`
- **Lines affected**: 247, 320, 383
- **Issue**: Query references company field

#### `backend/services/products_threats_service.py`
- **Lines affected**: 204, 255, 334, 362
- **Issue**: Query references company field

### 2. **Database Migration**

#### `backend/db/20260806-products-orgs-fk.sql`
- **Lines affected**: 2, 12, 16
- **Issue**: Migration script references `products.company` in comments and UPDATE logic
- **Code pattern**:
  ```sql
  -- Add Foreign Key: products.company -> orgs.name
  WHERE p.company = o.name
  ```
- **Fix**: Update comments and SQL to reference `company_from_fda_import_deprecated`

### 3. **Documentation**

#### `docs/PRODUCTS_SCHEMA.md`
- **Lines affected**: 18, 40, 55, 64, 87
- **Issue**: Schema documentation lists and describes `company` column
- **Code pattern**:
  ```markdown
  || company | TEXT | Manufacturer/company name |
  products.company = "ViTAA Medical Solutions, Inc."
  CREATE INDEX idx_products_company ON public.products(company);
  ```
- **Fix**: Update all references to new column name, note deprecation

### 4. **Test Files**

#### `backend/tests/test_org_merge_integration.py`
- **Lines affected**: 106-112, 106-112 (product insert statements don't use company column, so may be OK)
- **Issue**: Check if any SELECT statements reference company

## Decision Points

### A. Use `company_from_fda_import_deprecated` directly
**Pros**: 
- Minimal code change
- Column still exists and queryable
- Clear deprecation signal

**Cons**:
- Perpetuates deprecated data structure
- All new code must know to avoid this column

### B. Migrate to org-based lookups
**Pattern**: `SELECT orgs.name FROM products JOIN orgs ON products.org_id = orgs.id`

**Pros**:
- Normalizes data properly
- Eliminates redundancy
- Single source of truth (org.name)

**Cons**:
- More extensive refactoring
- Requires ensuring all products have valid org_id set
- Agent logic becomes more complex

## Recommendation
**Hybrid approach**:
1. Update load_products.py and migration script to use new column name (technical necessity)
2. Update agent/service queries to prefer org relationship when available
3. Fall back to deprecated column as needed
4. Add logging to track deprecation usage
5. Plan for org_id validation and migration

## Column Availability
**Currently in database**: ✅ `company_from_fda_import_deprecated`  
**Currently NOT in database**: ❌ `company` (removed as of this task)  
**Index status**: ✅ `idx_products_company_from_fda_import_deprecated` (renamed)
