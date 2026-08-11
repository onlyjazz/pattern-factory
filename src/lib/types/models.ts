/**
 * Pattern Factory Domain Model Types
 * TypeScript interfaces matching the database schema
 */

/**
 * Organization representing a company or entity
 */
export interface Organization {
  id: number;
  name: string;
  description?: string;
  stage?: string; // e.g., "Seed", "Series A", "Public"
  funding?: number; // Total funding amount in dollars
  date_funded?: string; // ISO timestamp
  date_founded?: string; // ISO timestamp
  linkedin_company_url?: string;
  content_source?: string; // e.g., "substack", "fda-devices"
  category_id?: number;
  content_url?: string;
  estimated_annual_sales?: number; // Estimated annual revenue in dollars
  employees?: number; // Number of employees
  headquarters?: string; // Headquarters location (city, country)
  created_at?: string; // ISO timestamp
  updated_at?: string; // ISO timestamp
  deleted_at?: string | null; // ISO timestamp or null for active records
}

/**
 * Product representing FDA-cleared AI-enabled medical device
 */
export interface Product {
  id: number;
  date_of_final_decision?: string; // ISO timestamp
  submission_number: string; // FDA submission ID (e.g., K254207)
  device: string; // Device name
  intended_use?: string; // FDA-approved general function/purpose of device
  indications_for_use?: string; // Specific medical conditions the device treats/diagnoses
  company?: string; // Manufacturer company name
  panel?: string; // FDA regulatory panel
  primary_product_code?: string; // FDA product code
  product_contact_1?: string; // LinkedIn profile URL
  product_contact_2?: string; // LinkedIn profile URL
  product_contact_3?: string; // LinkedIn profile URL
  device_description?: string; // Device description from OpenFDA
  superiority?: string; // Competitive advantage claims from FEELGOOD flow
  org_id?: number; // Foreign key to organizations
  created_at?: string; // ISO timestamp
  updated_at?: string; // ISO timestamp
  deleted_at?: string | null; // ISO timestamp or null for active records
}

/**
 * Person representing an individual (guest, employee, etc.)
 */
export interface Person {
  id: number;
  name: string;
  description?: string;
  linkedin_url?: string;
  job_description?: string;
  org_id?: number; // Foreign key to organizations
  content_source?: string; // e.g., "linkedin", "twitter", "website"
  created_at?: string; // ISO timestamp
  updated_at?: string; // ISO timestamp
  deleted_at?: string | null; // ISO timestamp or null for active records
}

/**
 * Pattern representing a business or technical pattern
 */
export interface Pattern {
  id: number;
  name: string;
  description?: string;
  kind: 'pattern' | 'anti-pattern';
  content_source?: string;
  story_md?: string; // Markdown-formatted story
  created_at?: string; // ISO timestamp
  updated_at?: string; // ISO timestamp
  deleted_at?: string | null; // ISO timestamp or null for active records
}

/**
 * Helper function to format currency values
 */
export function formatCurrency(value: number | undefined): string {
  if (value === undefined || value === null) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Helper function to check if organization has funding info
 */
export function hasFundingInfo(org: Organization): boolean {
  return !!(org.funding || org.date_funded || org.stage);
}

/**
 * Helper function to check if organization has revenue info
 */
export function hasRevenueInfo(org: Organization): boolean {
  return !!org.estimated_annual_sales;
}
