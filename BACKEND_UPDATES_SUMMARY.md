# Backend Updates: Normalized Products.company to org.name

## Overview
Updated all backend code to reference company name via the `org_id` relationship (joining to `orgs.name`) instead of the deprecated `products.company_from_fda_import_deprecated` column.

## Files Updated

### 1. Agent Files (pitboss/)

#### `backend/pitboss/feelgood.py` ✅
- **Change**: Updated `agent_validate_product_id()` SELECT queries
- **Line 98-107**: Modified both product ID and device name lookups to:
  - Include `p.org_id` in SELECT
  - Add `LEFT JOIN public.orgs o ON p.org_id = o.id`
  - Select `COALESCE(o.name, '') AS company` instead of `company`
- **Impact**: Company name is now resolved from org relationship
- **Validation**: Missing company check updated to reference org_id association

#### `backend/pitboss/profile.py` ✅
- **Change**: Added clarifying comment about company source
- **Line 458**: Comment indicates `company` is from org join in validateProductId
- **Impact**: Minimal change - agent uses data from previous agent's validated product dict

#### `backend/pitboss/competitors.py` ✅
- **Changes**:
  1. Added clarifying comment about company source (line 86)
  2. Updated `tool.upsertCompetitors()` to prefer org_id relationship:
     - Line 349: Retrieve `product_org_id` from product dict (set by validateProductId)
     - Lines 353-356: Use product's existing org_id if available
     - Lines 357-376: Fallback to org lookup by name if org_id missing
  3. Removed deprecated company column from INSERT statement:
     - Line 435: Changed `INSERT INTO public.products (device, org_id, submission_number, process_flag)` 
     - Removed `company` and `competitor_company` parameters (now just 3 params instead of 5)
- **Impact**: Competitor products created with org_id relationship, not company column

### 2. Data Loading Script

#### `backend/scripts/load_products.py` ✅
- **Change**: Removed deprecated company column from INSERT statement
- **Lines 119-150**: Updated upsert to:
  - Remove `company` from column list in INSERT
  - Remove `company = EXCLUDED.company` from ON CONFLICT DO UPDATE
  - Reduce parameterized values from 11 to 10
  - Added comment: "Company data is stored via org_id relationship (populated by separate org matching process)"
- **Impact**: CSV loader no longer writes to deprecated column
- **Note**: Assumes separate process handles org_id population from company names

### 3. Service Files (services/)

#### `backend/services/products_threats_service.py` ✅
- **Changes**:
  1. `get_single_product()` (line 181):
     - Changed `p.company` to `o.name AS company`
     - Now selects from joined org table
  
  2. `get_products_in_range()` (line 228):
     - Changed `p.company` to `o.name AS company`
     - All three queries already have proper org joins
  
  3. `sample_products()` (lines 281, 306):
     - Updated both branches (all_in_arms=true and false):
     - Changed `p.company` to `o.name AS company`
     - Fixed ranked_products CTE to select company from org join
- **Impact**: All product fetches now resolve company from org relationship

#### `backend/services/threat_selector_service.py` ✅
- **Change**: Updated `get_device_profile()` query
- **Lines 212-215**: Changed to:
  - Use `o.name AS company` instead of `p.company`
  - Added `LEFT JOIN public.orgs o ON p.org_id = o.id`
- **Impact**: Device profiles built with org-sourced company names

### 4. Database Migration

#### `backend/db/20260806-products-orgs-fk.sql` ✅
- **Changes**:
  1. Updated comment (line 2): Changed "products.company" to "products.org_id"
  2. Added clarification comment (line 4): "Matches products.company_from_fda_import_deprecated to orgs.name"
  3. Updated WHERE clause (line 17): Changed `p.company = o.name` to `p.company_from_fda_import_deprecated = o.name`
- **Impact**: Migration script now references deprecated column correctly

## Data Flow After Changes

### Product Validation Flow
1. `model.validateProductId` (feelgood.py)
   - Queries: `SELECT ... o.name AS company ... FROM products p LEFT JOIN orgs o ON p.org_id = o.id`
   - Stores: `message_body["product"]` dict with company name from org
   
2. Downstream agents receive product dict with:
   - `product["company"]` — company name from org join (not deprecated column)
   - `product["org_id"]` — organization ID for direct access if needed

### Product Creation Flow
1. `load_products.py` batch import
   - Inserts: `device, intended_use, indications_for_use, panel, primary_product_code, product_contact_1/2/3` 
   - **Does NOT insert**: company or org_id (handled separately)
   
2. Separate org matching process (future)
   - Populates `products.org_id` by matching to `orgs.name`
   - This replaces the deprecated CSV company column data

3. `tool.upsertCompetitors` (competitors.py)
   - Uses product's `org_id` to identify company org
   - Creates new products with only: `device, org_id, submission_number, process_flag`
   - No deprecated company column written

## Fallback/Safety Measures

1. **Org Join with LEFT JOIN** (in threat_selector_service.py)
   - Uses LEFT JOIN instead of INNER JOIN
   - Ensures queries don't fail if org_id is NULL
   - Returns NULL company if org not found

2. **Org Existence Validation**
   - Query requirements enforce: `o.deleted_at IS NULL` where present
   - Profile agent requires org relationship for products

3. **Validation Checks**
   - Updated validation in feelgood.py to check `company (via org_id)` 
   - Prevents execution if org relationship missing

## Migration Notes

### Column Deprecation Status
- ❌ `products.company` — **REMOVED** from database
- ✅ `products.company_from_fda_import_deprecated` — exists for reference/audit only
- ✅ `idx_products_company_from_fda_import_deprecated` — index renamed

### Compatibility
- All agent flows now compatible with normalized schema
- No direct references to deprecated `products.company` in code
- All queries use `o.name AS company` pattern for consistency

### Testing Recommendations
1. Verify org_id population from migration script
2. Test validateProductId with products that have/don't have org_id
3. Test competitor product creation (should not fail on missing company column)
4. Verify device profiles built correctly in threat selector
5. Check fallback behavior when org relationship missing

## Next Steps
1. Run migration script to populate org_id relationships
2. Validate all org_id values populated correctly
3. Execute integration tests to verify all flows work
4. Monitor logs for any deprecated column warnings
