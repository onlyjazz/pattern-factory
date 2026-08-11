#!/usr/bin/env python3
"""
Batch Enrichment Script for Organizations

Usage:
    python batch_enrich_orgs.py --id-range 1 50          # Enrich orgs with id between 1 and 50
    python batch_enrich_orgs.py --id-range 1 100         # Enrich orgs with id between 1 and 100
    python batch_enrich_orgs.py --confidence 0.75         # Auto-approve extractions >= 0.75
    python batch_enrich_orgs.py --id-range 1 50 --confidence 0.75
    python batch_enrich_orgs.py --output results.csv      # Save results to CSV

Flow:
    1. Fetch orgs from database (filtered by id range)
    2. For each org:
       a. validateOrgName: Confirm org exists in database
       b. searchForEnrichmentData: Search Exa for funding/revenue data
       c. verifyExtractionResults: Parse results with LLM, get confidence score
       d. If confidence >= threshold: auto-approve and call enrichOrgDatabase
       e. Else: save for manual review
    3. Log results: success, skipped, failed
    4. Export CSV report

Configuration:
    Script automatically loads from .env file in project root:
    - DATABASE_URL: PostgreSQL connection string
    - OPENAI_API_KEY: Required for LLM extraction (gpt-4o-mini)
    - EXA_API_KEY: Required for web search (Exa neural search API)
"""

import asyncio
import logging
import argparse
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
import sys
import os

# Load environment variables from .env file
from dotenv import load_dotenv

# Find and load .env file from project root
project_root = Path(__file__).parent.parent.parent  # pattern-factory/
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
else:
    # Fallback: try to load from current directory
    load_dotenv()

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import asyncpg
from pitboss.enrichment import (
    agent_validate_org_name,
    agent_search_for_enrichment_data,
    agent_verify_extraction_results,
    agent_enrich_org_database,
)

# ============================================================================
# Logging Setup
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/batch_enrich.log"),
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# Database Connection
# ============================================================================

async def get_db_connection():
    """
    Create async PostgreSQL connection from .env file.
    
    Loads DATABASE_URL from .env. If not set, falls back to individual
    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE variables.
    """
    try:
        # Try DATABASE_URL first, then fall back to individual PG* vars
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            conn = await asyncpg.connect(database_url)
        else:
            conn = await asyncpg.connect(
                host=os.getenv("PGHOST", "127.0.0.1"),
                port=int(os.getenv("PGPORT", 5432)),
                user=os.getenv("PGUSER", "pattern_factory"),
                password=os.getenv("PGPASSWORD", "314159"),
                database=os.getenv("PGDATABASE", "pattern-factory"),
            )
        logger.info("✅ Connected to PostgreSQL")
        return conn
    except Exception as e:
        logger.error(f"❌ Database connection failed: {str(e)}")
        logger.error(f"   DATABASE_URL={os.getenv('DATABASE_URL')}")
        logger.error(f"   Check .env file at: {Path(__file__).parent.parent.parent / '.env'}")
        raise


# ============================================================================
# Batch Enrichment
# ============================================================================

async def fetch_orgs_to_enrich(db: asyncpg.Connection, id_min: int, id_max: int) -> List[Dict[str, Any]]:
    """
    Fetch organizations from database with missing enrichment data.
    
    Args:
        db: asyncpg connection
        id_min: Minimum org ID (inclusive)
        id_max: Maximum org ID (inclusive)
    
    Returns:
        List of org records (id, name, estimated_annual_sales, funding)
    """
    query = """
        SELECT id, name, estimated_annual_sales, funding
        FROM public.orgs
        WHERE id BETWEEN $1 AND $2
            AND (estimated_annual_sales IS NULL OR estimated_annual_sales = 0 OR funding IS NULL OR funding = 0)
        ORDER BY id
    """
    
    orgs = await db.fetch(query, id_min, id_max)
    logger.info(f"📦 Fetched {len(orgs)} orgs to enrich (id between {id_min} and {id_max})")
    return [dict(org) for org in orgs]


async def enrich_single_org(
    db: asyncpg.Connection,
    org_id: int,
    org_name: str,
    confidence_threshold: float = 0.70,
) -> Dict[str, Any]:
    """
    Run the full ENRICH workflow for a single organization.
    
    Args:
        db: asyncpg connection
        org_id: Organization ID
        org_name: Organization name
        confidence_threshold: Auto-approve if extraction confidence >= threshold
    
    Returns:
        Result dict with status, decision, confidence, reason, extracted_data
    """
    result = {
        "org_id": org_id,
        "org_name": org_name,
        "status": "unknown",
        "stage": None,
        "decision": None,
        "confidence": None,
        "reason": None,
        "extracted_data": None,
        "error": None,
    }
    
    try:
        # Build message body for workflow
        message_body = {
            "raw_text": org_name,
            "_db": db,
        }
        
        # Stage 1: validateOrgName
        logger.info(f"  [1/4] Validating org name: {org_name}")
        result["stage"] = "validateOrgName"
        decision, confidence, reason = await agent_validate_org_name(message_body)
        logger.info(f"         Decision: {decision} (confidence: {confidence:.2f})")
        
        if decision != "yes":
            result["status"] = "skipped"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            logger.warning(f"  ❌ {reason}")
            return result
        
        # Stage 2: searchForEnrichmentData
        logger.info(f"  [2/4] Searching for enrichment data...")
        result["stage"] = "searchForEnrichmentData"
        decision, confidence, reason = await agent_search_for_enrichment_data(message_body)
        logger.info(f"         Decision: {decision} (confidence: {confidence:.2f})")
        
        if decision != "yes":
            result["status"] = "no_data_found"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            logger.warning(f"  ⚠️  {reason}")
            return result
        
        # Stage 3: verifyExtractionResults
        logger.info(f"  [3/4] Verifying extraction results with LLM...")
        result["stage"] = "verifyExtractionResults"
        decision, confidence, reason = await agent_verify_extraction_results(message_body)
        logger.info(f"         Decision: {decision} (confidence: {confidence:.2f})")
        
        if decision != "yes":
            result["status"] = "low_confidence"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            logger.warning(f"  ⚠️  Low confidence: {reason}")
            return result
        
        # Check confidence threshold for auto-approval
        extracted_data = message_body.get("extracted_data", {})
        extraction_confidence = message_body.get("extraction_confidence", 0.0)
        
        if extraction_confidence < confidence_threshold:
            result["status"] = "pending_review"
            result["decision"] = "yes"
            result["confidence"] = extraction_confidence
            result["reason"] = f"Extraction confidence {extraction_confidence:.2f} below threshold {confidence_threshold}"
            result["extracted_data"] = extracted_data
            logger.info(f"  ⏸️  Pending manual review (confidence: {extraction_confidence:.2f} < {confidence_threshold})")
            return result
        
        # Stage 4: enrichOrgDatabase (auto-approve)
        logger.info(f"  [4/4] Auto-approving and writing to database (confidence: {extraction_confidence:.2f})...")
        result["stage"] = "enrichOrgDatabase"
        
        # Set raw_text to empty for auto-approval (no user comment needed)
        message_body["raw_text"] = ""
        
        decision, confidence, reason = await agent_enrich_org_database(message_body)
        logger.info(f"         Decision: {decision} (confidence: {confidence:.2f})")
        
        if decision == "yes":
            result["status"] = "completed"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            result["extracted_data"] = extracted_data
            logger.info(f"  ✅ {reason}")
            return result
        else:
            result["status"] = "write_failed"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            result["extracted_data"] = extracted_data
            logger.error(f"  ❌ Database write failed: {reason}")
            return result
    
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.exception(f"  ❌ Exception during enrichment: {str(e)}")
        return result


async def batch_enrich(
    id_min: int,
    id_max: int,
    confidence_threshold: float = 0.70,
    output_csv: str = None,
) -> None:
    """
    Run batch enrichment for organization records in ID range.
    
    Args:
        id_min: Minimum org ID (inclusive)
        id_max: Maximum org ID (inclusive)
        confidence_threshold: Auto-approve if extraction confidence >= threshold
        output_csv: Optional path to save results CSV
    """
    db = None
    try:
        # Connect to database
        db = await get_db_connection()
        
        # Fetch orgs to enrich
        orgs = await fetch_orgs_to_enrich(db, id_min, id_max)
        
        if not orgs:
            logger.warning(f"❌ No orgs found to enrich in range [{id_min}, {id_max}]")
            return
        
        # Track results
        results = []
        stats = {
            "total": len(orgs),
            "completed": 0,
            "pending_review": 0,
            "skipped": 0,
            "no_data_found": 0,
            "low_confidence": 0,
            "error": 0,
        }
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Starting batch enrichment for {len(orgs)} organizations")
        logger.info(f"ID Range: [{id_min}, {id_max}]")
        logger.info(f"Confidence threshold: {confidence_threshold}")
        logger.info(f"{'='*80}\n")
        
        # Process each org
        for i, org in enumerate(orgs, 1):
            logger.info(f"\n[{i}/{len(orgs)}] Processing org ID {org['id']}: {org['name']}")
            
            result = await enrich_single_org(
                db,
                org["id"],
                org["name"],
                confidence_threshold=confidence_threshold,
            )
            
            results.append(result)
            stats[result["status"]] += 1
            
            # Small delay between requests to avoid rate limiting
            await asyncio.sleep(0.5)
        
        # Print summary
        logger.info(f"\n{'='*80}")
        logger.info("BATCH ENRICHMENT COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"Total processed:  {stats['total']}")
        logger.info(f"✅ Completed:      {stats['completed']}")
        logger.info(f"⏸️  Pending review: {stats['pending_review']}")
        logger.info(f"⚠️  No data found:  {stats['no_data_found']}")
        logger.info(f"⚠️  Low confidence: {stats['low_confidence']}")
        logger.info(f"⊘  Skipped:        {stats['skipped']}")
        logger.info(f"❌ Errors:         {stats['error']}")
        logger.info(f"{'='*80}\n")
        
        # Export results to CSV if requested
        if output_csv:
            export_results_csv(results, output_csv)
        
        # Print pending review items
        pending = [r for r in results if r["status"] == "pending_review"]
        if pending:
            logger.info(f"\n📋 {len(pending)} items pending manual review:")
            for r in pending:
                data = r.get("extracted_data", {})
                revenue = data.get("annual_revenue", "?")
                funding = data.get("total_funding_raised", "?")
                confidence = r.get("confidence", "?")
                logger.info(f"   - {r['org_name']}: revenue=${revenue:,}, funding=${funding:,}, confidence={confidence:.2f}")
    
    except Exception as e:
        logger.error(f"❌ Batch enrichment failed: {str(e)}", exc_info=True)
    finally:
        if db:
            await db.close()
            logger.info("Database connection closed")


def export_results_csv(results: List[Dict[str, Any]], output_path: str) -> None:
    """
    Export enrichment results to CSV file.
    
    Args:
        results: List of result dicts from batch_enrich
        output_path: Path to write CSV
    """
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "org_id",
                    "org_name",
                    "status",
                    "stage",
                    "decision",
                    "confidence",
                    "reason",
                    "extracted_data_json",
                    "error",
                ],
            )
            writer.writeheader()
            
            for result in results:
                writer.writerow({
                    "org_id": result["org_id"],
                    "org_name": result["org_name"],
                    "status": result["status"],
                    "stage": result["stage"],
                    "decision": result["decision"],
                    "confidence": result["confidence"],
                    "reason": result["reason"],
                    "extracted_data_json": json.dumps(result["extracted_data"]) if result["extracted_data"] else "",
                    "error": result["error"],
                })
        
        logger.info(f"✅ Results exported to {output_path}")
    except Exception as e:
        logger.error(f"❌ Failed to export results: {str(e)}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch enrich organization records using the ENRICH agent workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python batch_enrich_orgs.py --id-range 1 50           # Enrich orgs 1-50
  python batch_enrich_orgs.py --id-range 1 100 --confidence 0.75
  python batch_enrich_orgs.py --id-range 100 200 --output results.csv
        """,
    )
    
    parser.add_argument(
        "--id-range",
        nargs=2,
        type=int,
        metavar=("MIN", "MAX"),
        required=True,
        help="ID range: enrich orgs where id BETWEEN MIN AND MAX (inclusive)",
    )
    
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.70,
        help="Auto-approve if extraction confidence >= threshold (default: 0.70)",
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional: export results to CSV file",
    )
    
    args = parser.parse_args()
    
    id_min, id_max = args.id_range
    
    if id_min > id_max:
        logger.error(f"❌ Invalid range: {id_min} > {id_max}")
        sys.exit(1)
    
    if not (0.0 <= args.confidence <= 1.0):
        logger.error(f"❌ Confidence must be between 0.0 and 1.0, got {args.confidence}")
        sys.exit(1)
    
    # Run async batch enrichment
    asyncio.run(batch_enrich(
        id_min=id_min,
        id_max=id_max,
        confidence_threshold=args.confidence,
        output_csv=args.output,
    ))


if __name__ == "__main__":
    main()
