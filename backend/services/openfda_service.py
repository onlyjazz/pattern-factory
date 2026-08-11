"""
OpenFDA Integration Service

Fetches FDA 510(k) device descriptions from the OpenFDA API and populates
the products.device_description column in the database.

OpenFDA API Documentation:
- Base URL: https://api.fda.gov/device/510k.json
- Query: ?search=submission_number:"K123456"
- Public API: 240 requests/minute without key
- Key-authenticated: 1000+ requests/minute with API key
- Free key signup: https://open.fda.gov/apis/
"""

import asyncio
import aiohttp
import asyncpg
import logging
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger("openfda_service")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)

# OpenFDA Configuration
OPENFDA_BASE_URL = "https://api.fda.gov/device/510k.json"
OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY")  # Optional - for higher rate limits
REQUEST_TIMEOUT = 60  # seconds
RATE_LIMIT_DELAY = 0.25  # seconds (240 req/min = 1 req every 0.25 sec)
BATCH_SIZE = 10  # Concurrent requests per batch
RETRY_LIMIT = 3
RETRY_DELAY = 2  # seconds


@dataclass
class DeviceDescription:
    """Fetched device description from OpenFDA."""
    submission_number: str
    device_name: str
    applicant: str
    statement_or_description: str
    product_code: str
    success: bool = True
    error: Optional[str] = None


class OpenFDAClient:
    """HTTP client for OpenFDA API with rate limiting and retry logic."""
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = REQUEST_TIMEOUT):
        """Initialize OpenFDA client.
        
        Args:
            api_key: Optional OpenFDA API key for higher rate limits
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_count = 0
        self.last_request_time = 0
    
    async def __aenter__(self):
        """Context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _rate_limit(self):
        """Enforce rate limiting (240 req/min without key)."""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()
    
    async def fetch_device_description(
        self, submission_number: str, retry_count: int = 0
    ) -> DeviceDescription:
        """Fetch device description from OpenFDA API.
        
        Args:
            submission_number: FDA 510(k) submission number (e.g., "K191432")
            retry_count: Current retry attempt
        
        Returns:
            DeviceDescription with fetched data or error info
        """
        if not submission_number or not submission_number.startswith("K"):
            return DeviceDescription(
                submission_number=submission_number,
                device_name="",
                applicant="",
                statement_or_description="",
                product_code="",
                success=False,
                error=f"Invalid submission number format: {submission_number}"
            )
        
        try:
            await self._rate_limit()
            
            # Build URL
            query = f'submission_number:"{submission_number}"'
            params = {"search": query}
            if self.api_key:
                params["api_key"] = self.api_key
            
            if not self.session:
                raise RuntimeError("Session not initialized")
            
            async with self.session.get(
                OPENFDA_BASE_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as resp:
                logger.debug(f"OpenFDA API response: {resp.status} for {submission_number}")
                
                if resp.status == 404:
                    return DeviceDescription(
                        submission_number=submission_number,
                        device_name="",
                        applicant="",
                        statement_or_description="",
                        product_code="",
                        success=False,
                        error="Not found (404)"
                    )
                
                if resp.status == 429:
                    # Rate limited - retry with exponential backoff
                    if retry_count < RETRY_LIMIT:
                        wait_time = RETRY_DELAY * (2 ** retry_count)
                        logger.warning(
                            f"Rate limited for {submission_number}, "
                            f"retrying in {wait_time}s (attempt {retry_count + 1}/{RETRY_LIMIT})"
                        )
                        await asyncio.sleep(wait_time)
                        return await self.fetch_device_description(submission_number, retry_count + 1)
                    return DeviceDescription(
                        submission_number=submission_number,
                        device_name="",
                        applicant="",
                        statement_or_description="",
                        product_code="",
                        success=False,
                        error="Rate limited (429) - max retries exceeded"
                    )
                
                if resp.status != 200:
                    return DeviceDescription(
                        submission_number=submission_number,
                        device_name="",
                        applicant="",
                        statement_or_description="",
                        product_code="",
                        success=False,
                        error=f"HTTP {resp.status}"
                    )
                
                data = await resp.json()
                
                if not data.get("results"):
                    return DeviceDescription(
                        submission_number=submission_number,
                        device_name="",
                        applicant="",
                        statement_or_description="",
                        product_code="",
                        success=False,
                        error="No results found"
                    )
                
                record = data["results"][0]
                
                return DeviceDescription(
                    submission_number=submission_number,
                    device_name=record.get("device_name", ""),
                    applicant=record.get("applicant", ""),
                    statement_or_description=record.get("statement_or_description", ""),
                    product_code=record.get("product_code", ""),
                    success=True
                )
        
        except asyncio.TimeoutError:
            return DeviceDescription(
                submission_number=submission_number,
                device_name="",
                applicant="",
                statement_or_description="",
                product_code="",
                success=False,
                error="Request timeout"
            )
        except Exception as e:
            return DeviceDescription(
                submission_number=submission_number,
                device_name="",
                applicant="",
                statement_or_description="",
                product_code="",
                success=False,
                error=str(e)
            )


class OpenFDAService:
    """Service to fetch OpenFDA descriptions and populate database."""
    
    def __init__(self, db_url: str, api_key: Optional[str] = None):
        """Initialize service.
        
        Args:
            db_url: PostgreSQL connection URL
            api_key: Optional OpenFDA API key
        """
        self.db_url = db_url
        self.api_key = api_key
        self.client: Optional[OpenFDAClient] = None
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize database connection and HTTP client."""
        logger.info(f"Initializing OpenFDA service...")
        
        # Create database pool
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=1,
            max_size=5,
            command_timeout=60
        )
        logger.info("✓ Database pool created")
        
        # Create HTTP client
        self.client = OpenFDAClient(api_key=self.api_key)
        await self.client.__aenter__()
        logger.info("✓ OpenFDA HTTP client initialized")
    
    async def cleanup(self):
        """Close connections."""
        if self.client:
            await self.client.__aexit__(None, None, None)
        if self.pool:
            await self.pool.close()
        logger.info("✓ Connections closed")
    
    async def get_products_to_update(
        self, 
        product_ids: Optional[List[int]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get products that need device_description populated.
        
        Args:
            product_ids: Optional list of specific product IDs to update
            limit: Maximum number of products to retrieve
        
        Returns:
            List of product dicts with id, submission_number, device, company
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
                # Get products without descriptions
                products = await conn.fetch("""
                    SELECT id, submission_number, device, company
                    FROM public.products
                    WHERE deleted_at IS NULL 
                      AND (device_description IS NULL OR device_description = '')
                    ORDER BY id
                    LIMIT $1
                """, limit)
        
        return [dict(p) for p in products]
    
    async def populate_descriptions(
        self,
        product_ids: Optional[List[int]] = None,
        limit: int = 100,
        batch_size: int = BATCH_SIZE,
        use_fallback: bool = True
    ) -> Dict[str, Any]:
        """Fetch OpenFDA descriptions and populate database.
        
        Args:
            product_ids: Optional list of specific product IDs
            limit: Max products to process if product_ids not specified
            batch_size: Number of concurrent requests per batch
            use_fallback: If True, use device/company info as fallback when OpenFDA fails
        
        Returns:
            Summary dict with success/failure counts
        """
        if not self.client or not self.pool:
            raise RuntimeError("Service not initialized")
        
        # Get products to update
        products = await self.get_products_to_update(product_ids, limit)
        
        if not products:
            logger.info("No products to update")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "details": []
            }
        
        logger.info(f"Processing {len(products)} products (fallback={'enabled' if use_fallback else 'disabled'})...")
        
        results = {
            "total": len(products),
            "success": 0,
            "failed": 0,
            "fallback": 0,
            "skipped": 0,
            "details": []
        }
        
        # Process in batches
        for batch_start in range(0, len(products), batch_size):
            batch_end = min(batch_start + batch_size, len(products))
            batch = products[batch_start:batch_end]
            
            # Fetch descriptions concurrently
            tasks = [
                self.client.fetch_device_description(p["submission_number"])
                for p in batch
            ]
            descriptions = await asyncio.gather(*tasks)
            
            # Update database
            async with self.pool.acquire() as conn:
                for product, desc in zip(batch, descriptions):
                    try:
                        # Determine what description to use
                        device_description = None
                        source = "openfda"
                        
                        if desc.success:
                            # Got it from OpenFDA
                            device_description = desc.statement_or_description
                            source = "openfda"
                        elif use_fallback:
                            # Fall back to device + company info
                            device = product.get("device", "")
                            company = product.get("company", "")
                            if device and company:
                                device_description = f"{device} from {company}"
                                source = "fallback"
                                results["fallback"] += 1
                        
                        if not device_description:
                            results["failed"] += 1
                            results["details"].append({
                                "product_id": product["id"],
                                "submission_number": product["submission_number"],
                                "status": "failed",
                                "error": desc.error,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            logger.warning(
                                f"✗ Product {product['id']} ({product['submission_number']}): "
                                f"{desc.error}"
                            )
                            continue
                        
                        # Update product
                        await conn.execute(
                            """
                            UPDATE public.products
                            SET device_description = $1, updated_at = NOW()
                            WHERE id = $2
                            """,
                            device_description,
                            product["id"]
                        )
                        
                        results["success"] += 1
                        results["details"].append({
                            "product_id": product["id"],
                            "submission_number": product["submission_number"],
                            "status": "success",
                            "source": source,
                            "description_length": len(device_description),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        
                        logger.info(
                            f"✓ Product {product['id']} ({product['submission_number']}): "
                            f"{len(device_description)} chars from {source}"
                        )
                    
                    except Exception as e:
                        results["failed"] += 1
                        results["details"].append({
                            "product_id": product["id"],
                            "submission_number": product["submission_number"],
                            "status": "failed",
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        logger.error(
                            f"✗ Product {product['id']} database update failed: {e}"
                        )
            
            # Brief pause between batches
            if batch_end < len(products):
                await asyncio.sleep(1)
        
        logger.info(f"""
        
        ✅ OpenFDA Population Complete
        ├─ Total:   {results['total']}
        ├─ Success: {results['success']}
        ├─ Failed:  {results['failed']}
        └─ Skipped: {results['skipped']}
        """)
        
        return results


async def main():
    """CLI entry point for OpenFDA service."""
    import sys
    import json
    
    # Parse arguments
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    api_key = os.getenv("OPENFDA_API_KEY")
    if api_key:
        logger.info(f"✓ Using authenticated OpenFDA API (higher rate limit)")
    else:
        logger.info(f"ℹ Using public OpenFDA API (240 req/min)")
    
    # Parse product IDs from args
    product_ids = None
    limit = 100
    
    for arg in sys.argv[1:]:
        if arg.startswith("--product-ids="):
            ids_str = arg.split("=")[1]
            product_ids = [int(x.strip()) for x in ids_str.split(",")]
        elif arg.startswith("--range="):
            range_str = arg.split("=")[1]
            if "-" in range_str:
                start, end = map(int, range_str.split("-"))
                product_ids = list(range(start, end + 1))
        elif arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    
    # Initialize and run
    service = OpenFDAService(db_url, api_key)
    
    try:
        await service.initialize()
        results = await service.populate_descriptions(product_ids, limit)
        
        # Log results to database
        async with service.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.system_log (event_type, entity_table, entity_id, details)
                VALUES ($1, $2, $3, $4)
                """,
                "OPENFDA_POPULATION",
                "products",
                None,
                json.dumps(results)
            )
        
        sys.exit(0 if results["failed"] == 0 else 1)
    
    finally:
        await service.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
