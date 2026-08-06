# Products Schema: FDA AI-Enabled Medical Devices

## Overview

The products table (`public.products`) stores FDA-cleared artificial intelligence (AI) enabled medical devices. It serves as a registry of cleared devices with links to:
- **Organizations** (`orgs`): Via company name matching
- **Threat Models** (`threat.models`): Via submission_number for device-specific threat modeling

## Table Schema

```sql
CREATE TABLE public.products (
    id BIGSERIAL PRIMARY KEY,
    date_of_final_decision TIMESTAMP,
    submission_number TEXT NOT NULL UNIQUE,
    device TEXT NOT NULL,
    indicated_use TEXT,
    company TEXT,
    panel TEXT,
    primary_product_code TEXT,
    product_contact_1 TEXT,          -- LinkedIn profile URL
    product_contact_2 TEXT,          -- LinkedIn profile URL
    product_contact_3 TEXT,          -- LinkedIn profile URL
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP,
    search_vector tsvector           -- Full-text search index
);
```

## Column Definitions

| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Auto-incrementing primary key |
| date_of_final_decision | TIMESTAMP | FDA clearance/approval date |
| submission_number | TEXT | FDA submission ID (e.g., K254207) - UNIQUE |
| device | TEXT | Device name/product title |
| indicated_use | TEXT | FDA-approved intended use statement (NULL initially, agent-populated) |
| company | TEXT | Manufacturer/company name |
| panel | TEXT | FDA regulatory panel (Radiology, Cardiology, etc.) |
| primary_product_code | TEXT | FDA product code (e.g., QIH, JAK) |
| product_contact_1 | TEXT | LinkedIn profile URL of product owner/manager (NULL initially, agent-populated) |
| product_contact_2 | TEXT | LinkedIn profile URL of secondary contact (NULL initially, agent-populated) |
| product_contact_3 | TEXT | LinkedIn profile URL of tertiary contact (NULL initially, agent-populated) |
| created_at | TIMESTAMP | Row creation timestamp (auto-set) |
| updated_at | TIMESTAMP | Row last update timestamp (auto-maintained by trigger) |
| deleted_at | TIMESTAMP | Soft delete marker (NULL = active) |
| search_vector | tsvector | Full-text search vector (device + indicated_use + company) |

## Relationships

### Product ← → Organization

**Direction**: products.company → orgs.name (Non-enforced FK at DB level)

**Pattern**: Application-level matching via company name
- Product `company` field contains the exact organization name as it appears in `orgs.name`
- Enforced during CSV batch load
- Used for entity linking and organization profiles

**Example**:
```
products.company = "ViTAA Medical Solutions, Inc."
orgs.name = "ViTAA Medical Solutions, Inc."
```

### Product ← → Threat Model

**Direction**: products.submission_number ← → threat.models.submission_number

**Pattern**: One-to-one optional relationship
- Each product can be optionally linked to a threat model
- Threat models use `submission_number` to reference specific products
- Enables device-specific threat landscape modeling

**Example**:
```
products.submission_number = "K254207"
threat.models.submission_number = "K254207"
```

## Indexes

```sql
CREATE INDEX idx_products_submission_number ON public.products(submission_number);
CREATE INDEX idx_products_company ON public.products(company);
CREATE INDEX idx_products_active ON public.products(id) WHERE deleted_at IS NULL;
CREATE INDEX idx_products_vector ON public.products USING GIN (search_vector);
```

## Batch Loading

### Source Data

**File**: `backend/data/aiml-devices.csv`
**Source**: FDA Official AI-Enabled Medical Devices Registry
**URL**: https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-enabled-medical-devices

### CSV Format

```csv
Date of Final Decision,Submission Number,Device,Company,Panel (Lead),Primary Product Code
03/30/2026,K254207,AiORTA - Plan v2.0,"ViTAA Medical Solutions, Inc.",Radiology,QIH
03/28/2026,K252360,ECG-AI Pulmonary Hypertension (PH) 12-Lead algorithm (1020),"Anumana, Inc.",Cardiovascular,SAT
...
```

### Loader Script

**File**: `backend/scripts/load_products.py`

**Features**:
- Async asyncpg for high-performance loading
- ON CONFLICT upsert by submission_number (idempotent)
- Date parsing: MM/DD/YYYY → TIMESTAMP
- Dry-run validation mode
- Graceful error handling

**Usage**:

```bash
# Dry-run: preview without inserting
python backend/scripts/load_products.py --dry-run

# Load from default path
python backend/scripts/load_products.py

# Load from custom path
python backend/scripts/load_products.py --csv-path /path/to/custom.csv
```

## Data Population Strategy

### Batch Load (Immediate)

1. **Migration**: `20260806-products-schema.sql`
   - Creates table and indexes
   - Adds submission_number to threat.models

2. **CSV Load**: `load_products.py`
   - Reads backend/data/aiml-devices.csv
   - Populates: device, company, panel, primary_product_code, date_of_final_decision
   - Initializes as NULL: product_contact_1/2/3, indicated_use

### Agent Population (Future Cycles)

#### Indicated Use Population

**Trigger**: Agent extracts from FDA submission PDFs

**Source**: FDA CDRH database via submission_number
- URL pattern: `https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={submission_number}`
- PDF link: `https://www.accessdata.fda.gov/cdrh_docs/pdf##/{submission_number}.pdf`

**Process**:
1. Fetch FDA submission page
2. Extract PDF summary link
3. Parse PDF for "Indications for Use" or "Intended Use" section
4. Update products.indicated_use

**Example**:
```
K214036 → https://www.accessdata.fda.gov/cdrh_docs/pdf21/K214036.pdf
Extract: "Quantib™ Brain is a non-invasive medical imaging processing application 
         that is intended for automatic labeling, visualization, and volumetric 
         quantification of segmentable brain structures from a set of magnetic 
         resonance (MR) images."
```

#### Product Contact Population

**Trigger**: Agent Google search and LinkedIn scraping

**Search Pattern**: `"product manager" {device_name} {company_name}`

**Process**:
1. For each product, search: "[Product] [Company] product manager OR CEO"
2. Extract LinkedIn profiles from search results
3. Identify key stakeholders
4. Populate product_contact_1/2/3 with LinkedIn URLs

**Acquisition Tracking**:
- Detects when companies are acquired
- Updates company information in orgs table
- Tracks device ownership changes

**Example**:
```
Device: ClearView cCAD
Original Company: ClearView Diagnostics
Current Company: Koios Medical (acquired)
Contacts: Links to original and new stakeholders
```

## Full-Text Search

The `search_vector` column enables efficient full-text search across:
- Device name
- Indicated use
- Company name

**Query Example**:
```sql
SELECT * FROM public.products
WHERE search_vector @@ plainto_tsquery('english', 'cardiac imaging')
LIMIT 10;
```

## API Access

Products are immediately queryable via the FastAPI generic query endpoint:

```bash
# Get all products
curl http://localhost:8000/query/products

# Filter by submission number
curl "http://localhost:8000/query/products?submission_number=K254207"

# Search by company
curl "http://localhost:8000/query/products?company=Anumana"
```

## Soft Deletes

Products support soft deletion via the `deleted_at` column:
- `deleted_at IS NULL`: Active product
- `deleted_at IS NOT NULL`: Inactive/removed product

**Partial Index**: `idx_products_active` optimizes queries for active products only:
```sql
CREATE INDEX idx_products_active ON public.products(id) WHERE deleted_at IS NULL;
```

## Statistics

**Current Data** (as of 2026-08-06):
- Total Products: 1,524
- Unique Companies: 781
- Regulatory Panels: 18
  - Radiology (largest category)
  - Cardiovascular
  - Pathology
  - Gastroenterology
  - Orthopedic, Obstetric/Gynecology, Pulmonary/Respiratory, etc.

## Future Enhancements

1. **Monthly Refresh Cycle**
   - Download latest aiml-devices.csv from FDA
   - Re-run loader (upsert by submission_number)
   - Detect new products and changed information

2. **Frontend Integration**
   - Products index page with search/filter
   - Product detail view with organization linkage
   - Threat model associations
   - Timeline of acquisitions and ownership changes

3. **Company Enrichment**
   - Link products back to organization profiles
   - Create company timelines (when acquired products)
   - Track product portfolio by company

4. **Threat Model Integration**
   - Create device-specific threat landscapes
   - Link to organizational risk assessments
   - Model FDA regulatory risk
