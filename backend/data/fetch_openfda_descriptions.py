#!/usr/bin/env python3
"""
Fetch device descriptions from OpenFDA 510(k) API
and populate products.device_description column.

Usage:
    python fetch_openfda_descriptions.py [--product-ids 1,2,3] [--batch-size 10]
"""

import asyncio
import aiohttp
import asyncpg
import logging
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OpenFDA API Configuration
OPENFDA_BASE_URL = "https://api.fda.gov/device/510k.json"
REQUEST_TIMEOUT = 60
BATCH_SIZE = 10
RETRY_LIMIT = 3


async def get_openfda_description(session: aiohttp.ClientSession, submission_number: str) -> dict:
    """
    Fetch device description from OpenFDA API.
    
    Args:
        session: aiohttp session
        submission_number: FDA 510(k) submission number (e.g., "K191432")
    
    Returns:
        dict with keys: device_name, description, product_code
    """
    if not submission_number or not submission_number.startswith("K"):
        logger.warning(f"Invalid submission number format: {submission_number}")
        return {}
    
    # Construct query
    query = f'submission_number:"{submission_number}"'
    url = f"{OPENFDA_BASE_URL}?search={query}"
    
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
            if resp.status == 404:
                logger.warning(f"  [404] Submission {submission_number} not found")
                return {}
            
            if resp.status == 429:
                logger.warning(f"  [429] Rate limited - waiting before retry")
                await asyncio.sleep(5)
                return await get_openfda_description(session, submission_number)
            
            resp.raise_for_status()
            
            data = await resp.json()
            
            if not data.get("results"):
                logger.warning(f"  No results for {submission_number}")
                return {}
            
            record = data["results"][0]
            
            return {
                "device_name": record.get("device_name", ""),
                "description": record.get("statement_or_description", ""),
                "product_code": record.get("product_code", ""),
            }
            
    except aiohttp.ClientError as e:
        logger.error(f"  HTTP error fetching {submission_number}: {e}")
        return {}
    except Exception as e:
        logger.error(f"  Error fetching {submission_number}: {e}", exc_info=True)
        return {}


async def fetch_and_populate(product_ids=None, batch_size=BATCH_SIZE):
    """
    Fetch OpenFDA descriptions and populate products table.
    
    Args:
        product_ids: List of product IDs to process, or None for all products
        batch_size: Number of concurrent requests
    """
    # Connect to database
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        return
    
    pool = await asyncpg.create_pool(
        db_url,
        min_size=1,
        max_size=batch_size + 5,
        command_timeout=60
    )
    
    try:
        async with pool.acquire() as conn:
            # Get products to process
            if product_ids:
                # Specific product IDs
                placeholders = ", ".join(f"${i}" for i in range(1, len(product_ids) + 1))
                query = f"""
                    SELECT id, submission_number, device, company
                    FROM public.products
                    WHERE id IN ({placeholders}) AND deleted_at IS NULL
                    ORDER BY id
                """
                products = await conn.fetch(query, *product_ids)
            else:
                # All products
                products = await conn.fetch("""
                    SELECT id, submission_number, device, company
                    FROM public.products
                    WHERE deleted_at IS NULL AND device_description IS NULL
                    ORDER BY id
                    LIMIT 100
                """)
            
            if not products:
                logger.info("No products to process")
                return
            
            logger.info(f"Processing {len(products)} products...")
            
            # Fetch descriptions concurrently
            async with aiohttp.ClientSession() as session:
                tasks = []
                for product in products:
                    task = get_openfda_description(session, product["submission_number"])
                    tasks.append((product, task))
                
                # Process in batches
                for i in range(0, len(tasks), batch_size):
                    batch = tasks[i:i+batch_size]
                    
                    results = []
                    for product, task in batch:
                        try:
                            desc_data = await asyncio.wait_for(task, timeout=70)
                            results.append((product, desc_data))
                        except asyncio.TimeoutError:
                            logger.warning(f"  Timeout fetching {product['submission_number']}")
                            results.append((product, {}))
                    
                    # Update database
                    async with pool.acquire() as conn:
                        for product, desc_data in results:
                            description = desc_data.get("description", "")
                            
                            await conn.execute(
                                """
                                UPDATE public.products
                                SET device_description = $1, updated_at = NOW()
                                WHERE id = $2
                                """,
                                description if description else None,
                                product["id"]
                            )
                            
                            status = "✓" if description else "✗"
                            logger.info(
                                f"{status} Product {product['id']}: {product['submission_number']} "
                                f"({len(description)} chars)"
                            )
                    
                    # Brief pause between batches
                    if i + batch_size < len(tasks):
                        await asyncio.sleep(1)
            
            logger.info("✅ Population complete")
            
    finally:
        await pool.close()


def parse_product_ids(args):
    """Parse product IDs from command line arguments."""
    product_ids = None
    
    for arg in args:
        if arg.startswith("--product-ids="):
            ids_str = arg.split("=")[1]
            product_ids = [int(x.strip()) for x in ids_str.split(",")]
        elif arg.startswith("--range="):
            range_str = arg.split("=")[1]
            if "-" in range_str:
                start, end = map(int, range_str.split("-"))
                product_ids = list(range(start, end + 1))
    
    return product_ids


if __name__ == "__main__":
    product_ids = parse_product_ids(sys.argv[1:])
    
    logger.info(f"🚀 Starting OpenFDA description fetch...")
    if product_ids:
        logger.info(f"Processing product IDs: {product_ids}")
    else:
        logger.info("Processing all products without descriptions (first 100)")
    
    asyncio.run(fetch_and_populate(product_ids=product_ids))
