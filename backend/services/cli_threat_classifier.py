#!/usr/bin/env python3
"""
CLI: Classify threats to countermeasure control classes.

Usage:
    ./bin/classify-threats --threat-ids=1,50 --model-id=35 [--min-confidence=0.6]

Examples:
    ./bin/classify-threats --threat-ids=1,150 --model-id=35
    ./bin/classify-threats --threat-ids=1,50,100,150 --model-id=35 --min-confidence=0.7
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List

import asyncpg
from dotenv import load_dotenv
from openai import OpenAI

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from threat_classifier_service import (
    classify_threats_batch,
    fetch_countermeasure_classes,
    upsert_threat_classifications,
    log_classification_event,
)

load_dotenv()

logger = logging.getLogger("classify_threats_cli")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://pattern_factory@localhost/pattern-factory",
)
DEFAULT_MODEL_ID = 35


def parse_threat_ids(threat_ids_arg: str) -> List[int]:
    """Parse threat ID argument (range or list)."""
    if "," in threat_ids_arg:
        # Comma-separated list
        return [int(x.strip()) for x in threat_ids_arg.split(",") if x.strip()]
    elif "-" in threat_ids_arg:
        # Range: "1-50" -> [1, 2, ..., 50]
        parts = threat_ids_arg.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid range format: {threat_ids_arg}")
        start, end = int(parts[0]), int(parts[1])
        return list(range(start, end + 1))
    else:
        # Single ID
        return [int(threat_ids_arg)]


async def main():
    parser = argparse.ArgumentParser(
        description="Classify threats to countermeasure control classes (PAT-330)"
    )
    parser.add_argument(
        "--threat-ids",
        required=True,
        help="Threat IDs to classify (range: '1,50' or list: '1,5,10,20')",
    )
    parser.add_argument(
        "--model-id",
        type=int,
        default=None,
        help="Threat model ID (optional; if omitted, classify across all models in threat range)",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum confidence threshold (default: 0.6)",
    )
    parser.add_argument(
        "--db-url",
        default=DEFAULT_DB_URL,
        help="Database URL (default: from DATABASE_URL env)",
    )
    parser.add_argument(
        "--no-upsert",
        action="store_true",
        help="Run classification but do not upsert to database",
    )
    
    args = parser.parse_args()
    
    # Parse threat IDs
    try:
        threat_ids = parse_threat_ids(args.threat_ids)
    except ValueError as e:
        print(f"Error parsing threat IDs: {e}", file=sys.stderr)
        sys.exit(1)
    
    logger.info(f"Classifying {len(threat_ids)} threats: {threat_ids[:10]}...")
    if args.model_id:
        logger.info(f"Model ID: {args.model_id}, Min Confidence: {args.min_confidence}")
    else:
        logger.info(f"Multi-model classification across threat range, Min Confidence: {args.min_confidence}")
    
    # Initialize database pool and OpenAI client
    pool = await asyncpg.create_pool(args.db_url, min_size=1, max_size=5)
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    try:
        # Step 1: Classify threats
        print("\n=== PAT-330: Threat Classification ===\n")
        print(f"Step 1: Classifying {len(threat_ids)} threats...")
        
        threat_to_classes = await classify_threats_batch(
            threat_ids=threat_ids,
            model_id=args.model_id,  # Can be None for multi-model
            db_pool=pool,
            openai_client=openai_client,
            min_confidence=args.min_confidence,
        )
        
        if not threat_to_classes:
            print("No threats classified.", file=sys.stderr)
            sys.exit(1)
        
        # Step 2: Analyze results
        print(f"\nStep 2: Analysis")
        class_counts = {}
        undefined_count = 0
        
        for threat_id, classes in threat_to_classes.items():
            for cls in classes:
                if cls == "UNDEFINED":
                    undefined_count += 1
                class_counts[cls] = class_counts.get(cls, 0) + 1
        
        print(f"  Total classifications: {sum(class_counts.values())}")
        print(f"  Total threats: {len(threat_to_classes)}")
        print(f"  Multi-class assignments: {sum(len(c) for c in threat_to_classes.values()) - len(threat_to_classes)}")
        print(f"  UNDEFINED count: {undefined_count}")
        
        print(f"\n  Class distribution:")
        for cls, count in sorted(class_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {cls}: {count}")
        
        if args.no_upsert:
            print("\n⚠ Skipping database upsert (--no-upsert flag set)")
            print(f"\nResults (first 10 threats):")
            for threat_id, classes in list(threat_to_classes.items())[:10]:
                print(f"  {threat_id}: {classes}")
            return
        
        # Step 3: Upsert to database
        print(f"\nStep 3: Upserting to database...")
        class_map = await fetch_countermeasure_classes(pool)
        inserted, skipped = await upsert_threat_classifications(
            pool,
            threat_to_classes,
            class_map,
        )
        
        print(f"  Inserted: {inserted}, Skipped: {skipped}")
        
        # Step 4: Log event
        event_context = {
            "threat_ids_count": len(threat_ids),
            "threat_ids_range": f"{min(threat_ids)}-{max(threat_ids)}",
            "model_id": args.model_id,
            "classifications_count": len(threat_to_classes),
            "multi_class_count": sum(len(c) for c in threat_to_classes.values()) - len(threat_to_classes),
            "undefined_count": undefined_count,
            "class_distribution": class_counts,
        }
        
        logged = await log_classification_event(
            pool,
            "THREAT_CLASSIFICATION_COMPLETE",
            event_context,
        )
        
        if logged:
            print(f"  Event logged to system_log")
        
        print(f"\n✅ Classification complete!\n")
        
    except Exception as e:
        logger.error(f"Classification failed: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
