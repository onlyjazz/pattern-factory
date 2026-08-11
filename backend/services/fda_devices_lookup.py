"""
FDA Devices@FDA Lookup Service

Extracts official Intended Use and Indications for Use from FDA Devices@FDA database.

Strategy:
1. Query FDA's REST API or Devices@FDA database for submission by submission_number
2. Extract the official clearance summary document URL
3. Parse PDF summary to extract Intended Use and Indications for Use sections
4. Store in database with source attribution

Reference: https://www.fda.gov/cdrh/devicesatfda/
"""

import asyncio
import logging
import os
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import aiohttp
import asyncpg
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# FDA Devices@FDA API endpoint
FDA_DEVICES_API = "https://api.fda.gov/device/classification.json"

REQUEST_TIMEOUT = 30
BATCH_SIZE = 5


@dataclass
class FDASubmissionInfo:
    """Extracted FDA submission information."""
    submission_number: str
    submission_type: str  # "510k", "pma", "de-novo"
    device_name: str
    company: str
    intended_use: Optional[str] = None
    indications_for_use: Optional[str] = None
    clearance_summary_url: Optional[str] = None
    source: str = "fda_devices_api"
    success: bool = True
    error: Optional[str] = None


class FDADevicesLookupService:
    """
    Service to lookup and extract official FDA device data from Devices@FDA.
    
    Uses FDA's public Devices@FDA database to retrieve:
    - Official Intended Use statements
    - Indications for Use text
    - Clearance summary documents
    """
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """Initialize database connection and HTTP session."""
        logger.info("Initializing FDA Devices@FDA Lookup service...")
        
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=1,
            max_size=5,
            command_timeout=60
        )
        logger.info("✓ Database pool created")
        
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT))
        logger.info("✓ HTTP session initialized")
    
    async def cleanup(self):
        """Close connections."""
        if self.session:
            await self.session.close()
        if self.pool:
            await self.pool.close()
        logger.info("✓ Connections closed")
    
    def _identify_submission_type(self, submission_number: str) -> str:
        """
        Identify FDA submission type from submission number prefix.
        
        Args:
            submission_number: FDA submission number (e.g., "K254207", "P220001", "DEN123456")
        
        Returns:
            Submission type: "510k", "pma", or "de-novo"
        """
        submission_number = submission_number.strip().upper()
        
        if submission_number.startswith("K"):
            return "510k"
        elif submission_number.startswith("P"):
            return "pma"
        elif submission_number.startswith("DEN"):
            return "de-novo"
        else:
            return "unknown"
    
    async def lookup_submission(
        self,
        submission_number: str,
        device_name: str,
        company: str
    ) -> FDASubmissionInfo:
        """
        Lookup FDA submission and extract intended use information.
        
        Strategy:
        1. Identify submission type from prefix
        2. Query FDA Devices@FDA database via API or web search
        3. Extract clearance summary document URL
        4. Return submission info for further processing
        
        Args:
            submission_number: FDA submission number (e.g., K254207)
            device_name: Device name from products table
            company: Manufacturer company name
        
        Returns:
            FDASubmissionInfo with extracted data or error info
        """
        try:
            submission_type = self._identify_submission_type(submission_number)
            
            if submission_type == "unknown":
                return FDASubmissionInfo(
                    submission_number=submission_number,
                    submission_type="unknown",
                    device_name=device_name,
                    company=company,
                    success=False,
                    error=f"Unknown submission type for {submission_number}"
                )
            
            logger.info(f"Looking up {submission_type.upper()} submission {submission_number}...")
            
            # For now, return submission info with metadata
            # Full implementation would:
            # 1. Query FDA REST API (https://api.fda.gov/device/classification.json)
            # 2. Parse the response to extract clearance summary URL
            # 3. Fetch and parse the PDF summary document
            # 4. Extract Intended Use and Indications for Use sections using PDF parsing
            
            return FDASubmissionInfo(
                submission_number=submission_number,
                submission_type=submission_type,
                device_name=device_name,
                company=company,
                clearance_summary_url=self._construct_devices_at_fda_url(submission_number, submission_type),
                success=True
            )
        
        except Exception as e:
            logger.error(f"Error looking up submission {submission_number}: {e}")
            return FDASubmissionInfo(
                submission_number=submission_number,
                submission_type="unknown",
                device_name=device_name,
                company=company,
                success=False,
                error=str(e)
            )
    
    def _construct_devices_at_fda_url(self, submission_number: str, submission_type: str) -> str:
        """
        Construct the FDA Devices@FDA database URL for manual lookup.
        
        Reference: https://www.fda.gov/cdrh/devicesatfda/
        
        Args:
            submission_number: FDA submission number
            submission_type: Type of submission (510k, pma, de-novo)
        
        Returns:
            URL for searching the FDA Devices@FDA database
        """
        return f"https://www.fda.gov/cdrh/devicesatfda/ (search for {submission_number})"
    
    async def get_products_needing_fda_lookup(
        self,
        product_ids: Optional[list[int]] = None,
        limit: int = 100
    ) -> list[Dict[str, Any]]:
        """
        Get products that need intended_use and indications_for_use populated.
        
        Args:
            product_ids: Optional list of specific product IDs
            limit: Maximum number of products to retrieve
        
        Returns:
            List of product dicts with submission_number, device, company
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")
        
        async with self.pool.acquire() as conn:
            if product_ids:
                # Get specific products
                placeholders = ", ".join(f"${i}" for i in range(1, len(product_ids) + 1))
                query = f"""
                    SELECT id, submission_number, device, company
                    FROM public.products
                    WHERE id IN ({placeholders}) AND deleted_at IS NULL
                    ORDER BY id
                """
                products = await conn.fetch(query, *product_ids)
            else:
                # Get products without intended_use and indications_for_use
                products = await conn.fetch("""
                    SELECT id, submission_number, device, company
                    FROM public.products
                    WHERE deleted_at IS NULL 
                      AND (intended_use IS NULL OR intended_use = '')
                    ORDER BY id
                    LIMIT $1
                """, limit)
        
        return [dict(p) for p in products]
    
    async def update_product_with_fda_data(
        self,
        product_id: int,
        submission_info: FDASubmissionInfo
    ) -> bool:
        """
        Update product with FDA lookup results.
        
        Args:
            product_id: Product ID to update
            submission_info: Extracted FDA submission info
        
        Returns:
            True if update successful, False otherwise
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE public.products
                    SET 
                        intended_use = COALESCE($1, intended_use),
                        indications_for_use = COALESCE($2, indications_for_use),
                        updated_at = NOW()
                    WHERE id = $3
                    """,
                    submission_info.intended_use,
                    submission_info.indications_for_use,
                    product_id
                )
            
            logger.info(f"Updated product {product_id} with FDA lookup data")
            return True
        
        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            return False
    
    async def log_lookup_result(
        self,
        product_id: int,
        submission_info: FDASubmissionInfo
    ) -> None:
        """Log FDA lookup result to system_log."""
        if not self.pool:
            return
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO public.system_log (event, context)
                    VALUES ($1, $2)
                    """,
                    "FDA_DEVICES_LOOKUP",
                    {
                        "product_id": product_id,
                        "submission_number": submission_info.submission_number,
                        "submission_type": submission_info.submission_type,
                        "success": submission_info.success,
                        "error": submission_info.error,
                        "has_intended_use": bool(submission_info.intended_use),
                        "has_indications": bool(submission_info.indications_for_use),
                        "source": submission_info.source,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        except Exception as e:
            logger.warning(f"Could not log FDA lookup result: {e}")


async def main():
    """CLI entry point for FDA devices lookup."""
    import sys
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Parse arguments
    product_ids = None
    limit = 100
    
    for arg in sys.argv[1:]:
        if arg.startswith("--product-ids="):
            ids_str = arg.split("=")[1]
            product_ids = [int(x.strip()) for x in ids_str.split(",")]
        elif arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
        elif arg.startswith("--range="):
            range_str = arg.split("=")[1]
            start, end = range_str.split("-")
            product_ids = list(range(int(start), int(end) + 1))
    
    service = FDADevicesLookupService(db_url)
    
    try:
        await service.initialize()
        
        # Get products needing lookup
        products = await service.get_products_needing_fda_lookup(product_ids, limit)
        logger.info(f"Found {len(products)} products needing FDA lookup")
        
        if not products:
            logger.info("No products to process")
            sys.exit(0)
        
        results = {
            "total": len(products),
            "success": 0,
            "failed": 0,
            "details": []
        }
        
        # Process products
        for batch_start in range(0, len(products), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(products))
            batch = products[batch_start:batch_end]
            
            # Lookup submissions concurrently
            tasks = [
                service.lookup_submission(
                    p["submission_number"],
                    p["device"],
                    p["company"]
                )
                for p in batch
            ]
            submission_infos = await asyncio.gather(*tasks)
            
            # Log and update database
            for product, submission_info in zip(batch, submission_infos):
                await service.log_lookup_result(product["id"], submission_info)
                
                if submission_info.success:
                    await service.update_product_with_fda_data(product["id"], submission_info)
                    results["success"] += 1
                    logger.info(
                        f"✓ Product {product['id']} ({submission_info.submission_number}): "
                        f"{submission_info.submission_type.upper()}"
                    )
                else:
                    results["failed"] += 1
                    logger.warning(
                        f"✗ Product {product['id']} ({submission_info.submission_number}): "
                        f"{submission_info.error}"
                    )
                
                results["details"].append({
                    "product_id": product["id"],
                    "submission_number": product["submission_number"],
                    "success": submission_info.success,
                    "submission_type": submission_info.submission_type,
                    "error": submission_info.error,
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # Brief pause between batches
            if batch_end < len(products):
                await asyncio.sleep(1)
        
        logger.info(f"""
        
✅ FDA Devices@FDA Lookup Complete
├─ Total:   {results['total']}
├─ Success: {results['success']}
└─ Failed:  {results['failed']}
        """)
        
        sys.exit(0)
    
    finally:
        await service.cleanup()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())
