#!/usr/bin/env python3
"""
Load FDA AI-enabled medical devices from CSV into the products table.

Usage:
    python load_products.py                    # Load from default path
    python load_products.py --csv-path /path   # Load from custom path
    python load_products.py --dry-run           # Preview without inserting
"""

import csv
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import argparse

try:
    import asyncpg
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: Missing required package. Install with: pip install asyncpg python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pattern_factory:314159@localhost:5432/pattern-factory")
DEFAULT_CSV_PATH = Path(__file__).parent.parent / "data" / "aiml-devices.csv"


async def get_connection():
    """Create async postgres connection."""
    return await asyncpg.connect(DATABASE_URL)


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date from MM/DD/YYYY format."""
    if not date_str or not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), "%m/%d/%Y")
    except ValueError:
        print(f"Warning: Could not parse date '{date_str}'")
        return None


async def load_products_from_csv(csv_path: str, dry_run: bool = False) -> int:
    """
    Load products from CSV file into database.
    
    Args:
        csv_path: Path to aiml-devices.csv
        dry_run: If True, print rows without inserting
    
    Returns:
        Number of rows processed
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"Error: CSV file not found: {csv_path}")
        return 0
    
    # Read CSV file
    rows_to_insert = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, 1):
            # Parse CSV columns
            date_of_final_decision = parse_date(row.get("Date of Final Decision", ""))
            submission_number = row.get("Submission Number", "").strip()
            device = row.get("Device", "").strip()
            company = row.get("Company", "").strip()
            panel = row.get("Panel (Lead)", "").strip()
            primary_product_code = row.get("Primary Product Code", "").strip()
            
            # Skip rows without critical fields
            if not submission_number or not device:
                print(f"Skipping row {idx}: missing submission_number or device")
                continue
            
            rows_to_insert.append({
                "date_of_final_decision": date_of_final_decision,
                "submission_number": submission_number,
                "device": device,
                "intended_use": None,  # Will be populated by FDA Primary Source service
                "indications_for_use": None,  # Will be populated by FDA Primary Source service
                "company": company,
                "panel": panel,
                "primary_product_code": primary_product_code,
                "product_contact_1": None,  # Will be populated by agent later
                "product_contact_2": None,  # Will be populated by agent later
                "product_contact_3": None,  # Will be populated by agent later
            })
    
    if not rows_to_insert:
        print("No valid rows found in CSV")
        return 0
    
    print(f"Read {len(rows_to_insert)} rows from CSV")
    
    if dry_run:
        print("\nDry-run mode: showing first 5 rows to insert:")
        for i, row in enumerate(rows_to_insert[:5], 1):
            print(f"\n{i}. {row['device']} ({row['submission_number']}) - {row['company']}")
        print(f"\n... and {len(rows_to_insert) - 5} more rows")
        return len(rows_to_insert)
    
    # Insert into database
    conn = await get_connection()
    try:
        inserted_count = 0
        skipped_count = 0
        
        for row in rows_to_insert:
            try:
                # Upsert: insert or update if submission_number exists
                result = await conn.execute("""
                    INSERT INTO public.products (
                        date_of_final_decision,
                        submission_number,
                        device,
                        intended_use,
                        indications_for_use,
                        company,
                        panel,
                        primary_product_code,
                        product_contact_1,
                        product_contact_2,
                        product_contact_3
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (submission_number) DO UPDATE SET
                        device = EXCLUDED.device,
                        company = EXCLUDED.company,
                        panel = EXCLUDED.panel,
                        primary_product_code = EXCLUDED.primary_product_code,
                        updated_at = now()
                """,
                    row["date_of_final_decision"],
                    row["submission_number"],
                    row["device"],
                    row["intended_use"],
                    row["indications_for_use"],
                    row["company"],
                    row["panel"],
                    row["primary_product_code"],
                    row["product_contact_1"],
                    row["product_contact_2"],
                    row["product_contact_3"],
                )
                inserted_count += 1
            except asyncpg.UniqueViolationError:
                skipped_count += 1
            except Exception as e:
                print(f"Error inserting {row['submission_number']}: {e}")
                skipped_count += 1
        
        print(f"\n✓ Inserted/updated {inserted_count} products")
        if skipped_count > 0:
            print(f"  (Skipped {skipped_count} due to errors or duplicates)")
        
        return inserted_count
    
    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Load FDA AI devices from CSV")
    parser.add_argument(
        "--csv-path",
        type=str,
        default=str(DEFAULT_CSV_PATH),
        help=f"Path to CSV file (default: {DEFAULT_CSV_PATH})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without inserting"
    )
    
    args = parser.parse_args()
    
    count = await load_products_from_csv(args.csv_path, dry_run=args.dry_run)
    sys.exit(0 if count > 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
