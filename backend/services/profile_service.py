"""
PROFILE Service - Extract FDA Device Profiles

Runs the PROFILE agent flow to populate the products table with:
- device_description: Official FDA device description
- intended_use: General function/purpose of the device
- indications_for_use: Specific medical conditions treated/diagnosed

Flow:
  1. model.validateProductId       - Verify product exists in database
  2. model.searchFDADatabase       - Search FDA Devices@FDA via Exa with domain filtering
  3. model.extractDeviceProfile   - Extract profile data using LLM
  4. tool.updateProductProfile    - Write profile to database

This service is designed to be run:
- Via CLI for batch processing
- Via WebSocket for real-time updates
- Via scheduled jobs for continuous enrichment
"""

import asyncio
import asyncpg
import logging
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("profile_service")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)

# Import pitboss components
from pitboss.agents import call_agent
from pitboss.workflow import WorkflowEngine


@dataclass
class ProfileResult:
    """Result of a single PROFILE flow execution."""
    product_id: int
    submission_number: str
    status: str  # "success", "failed", "partial"
    device_description: Optional[str] = None
    intended_use: Optional[str] = None
    indications_for_use: Optional[str] = None
    fields_extracted: int = 0  # 0-3 fields extracted
    error: Optional[str] = None
    agents_executed: List[str] = None
    timestamp: str = None


class ProfileService:
    """Service to run PROFILE agent flow for products."""
    
    def __init__(self, db_url: str):
        """Initialize service.
        
        Args:
            db_url: PostgreSQL connection URL
        """
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None
        self.workflow_engine: Optional[WorkflowEngine] = None
    
    async def initialize(self):
        """Initialize database connection and workflow engine."""
        logger.info("Initializing PROFILE Service...")
        
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=1,
            max_size=5,
            command_timeout=120
        )
        logger.info("✓ Database pool created")
        
        self.workflow_engine = WorkflowEngine()
        logger.info("✓ Workflow engine initialized")
    
    async def cleanup(self):
        """Close connections."""
        if self.pool:
            await self.pool.close()
        logger.info("✓ Connections closed")
    
    async def get_products_to_process(
        self,
        product_ids: Optional[List[int]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get products that need FDA device profiles.
        
        Args:
            product_ids: Optional list of specific product IDs
            limit: Maximum number of products to retrieve
        
        Returns:
            List of product dicts with required fields
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")
        
        async with self.pool.acquire() as conn:
            if product_ids:
                # Get specific products
                placeholders = ", ".join(f"${i}" for i in range(1, len(product_ids) + 1))
                query = f"""
                    SELECT id, submission_number, device, company, 
                           device_description, intended_use, indications_for_use
                    FROM public.products
                    WHERE id IN ({placeholders}) AND deleted_at IS NULL
                    ORDER BY id
                """
                products = await conn.fetch(query, *product_ids)
            else:
                # Get products without complete FDA profiles (missing intended_use or indications_for_use)
                products = await conn.fetch("""
                    SELECT id, submission_number, device, company,
                           device_description, intended_use, indications_for_use
                    FROM public.products
                    WHERE deleted_at IS NULL 
                      AND submission_number IS NOT NULL
                      AND (intended_use IS NULL OR indications_for_use IS NULL)
                    ORDER BY id
                    LIMIT $1
                """, limit)
        
        return [dict(p) for p in products]
    
    async def run_profile_flow(
        self,
        product: Dict[str, Any]
    ) -> ProfileResult:
        """Run PROFILE flow for a single product.
        
        Args:
            product: Product dict with id, submission_number, device, company, etc
        
        Returns:
            ProfileResult with device profile data and execution status
        """
        product_id = product["id"]
        submission_number = product["submission_number"]
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🚀 Starting PROFILE flow for Product {product_id} ({submission_number})")
        logger.info(f"{'='*70}")
        
        agents_executed = []
        
        try:
            # Initialize message body with product data
            message_body = {
                "product_id": product_id,
                "submission_number": submission_number,
                "product": product,
                "_db": self.pool,  # Pass pool for database access
                "raw_text": f"profile {product_id}",
                "verb": "PROFILE"
            }
            
            current_agent = "model.Capo"
            workflow = self.workflow_engine.get_workflow("PROFILE")
            
            # Run PROFILE workflow
            max_iterations = 10
            iteration = 0
            
            while not self.workflow_engine.is_terminal(current_agent) and iteration < max_iterations:
                iteration += 1
                agents_executed.append(current_agent)
                
                logger.info(f"\n[Step {iteration}] Calling {current_agent}...")
                
                try:
                    # Call agent
                    decision, confidence, reason = await call_agent(
                        current_agent,
                        "PROFILE",
                        message_body
                    )
                    
                    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
                    logger.info(f"  Reason: {reason}")
                    
                    # Get next agent
                    next_agent = self.workflow_engine.get_next_agent("PROFILE", current_agent, decision)
                    
                    if self.workflow_engine.is_terminal(next_agent):
                        logger.info(f"  → Terminal: {next_agent}")
                        break
                    
                    current_agent = next_agent
                    
                except Exception as e:
                    logger.error(f"❌ Agent {current_agent} failed: {e}", exc_info=True)
                    return ProfileResult(
                        product_id=product_id,
                        submission_number=submission_number,
                        status="failed",
                        error=str(e),
                        agents_executed=agents_executed,
                        timestamp=datetime.utcnow().isoformat()
                    )
            
            # Check for extracted profile
            device_profile = message_body.get("device_profile")
            
            if not device_profile:
                return ProfileResult(
                    product_id=product_id,
                    submission_number=submission_number,
                    status="failed",
                    error="No device profile extracted",
                    agents_executed=agents_executed,
                    timestamp=datetime.utcnow().isoformat()
                )
            
            # Count fields extracted
            fields_extracted = sum([
                bool(device_profile.get("device_description")),
                bool(device_profile.get("intended_use")),
                bool(device_profile.get("indications_for_use"))
            ])
            
            status = "success" if fields_extracted > 0 else "failed"
            
            logger.info(f"\n✅ PROFILE flow completed")
            logger.info(f"   Fields extracted: {fields_extracted}/3")
            if device_profile.get("device_description"):
                logger.info(f"   - device_description: {len(device_profile['device_description'])} chars")
            if device_profile.get("intended_use"):
                logger.info(f"   - intended_use: {len(device_profile['intended_use'])} chars")
            if device_profile.get("indications_for_use"):
                logger.info(f"   - indications_for_use: {len(device_profile['indications_for_use'])} chars")
            
            return ProfileResult(
                product_id=product_id,
                submission_number=submission_number,
                status=status,
                device_description=device_profile.get("device_description"),
                intended_use=device_profile.get("intended_use"),
                indications_for_use=device_profile.get("indications_for_use"),
                fields_extracted=fields_extracted,
                agents_executed=agents_executed,
                timestamp=datetime.utcnow().isoformat()
            )
        
        except Exception as e:
            logger.error(f"❌ PROFILE flow crashed: {e}", exc_info=True)
            return ProfileResult(
                product_id=product_id,
                submission_number=submission_number,
                status="failed",
                error=str(e),
                agents_executed=agents_executed,
                timestamp=datetime.utcnow().isoformat()
            )
    
    async def process_products(
        self,
        product_ids: Optional[List[int]] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Process multiple products through PROFILE flow.
        
        Args:
            product_ids: Optional list of specific product IDs
            limit: Max products to process if product_ids not specified
        
        Returns:
            Summary dict with results
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")
        
        # Get products to process
        products = await self.get_products_to_process(product_ids, limit)
        
        if not products:
            logger.info("No products to process")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "partial": 0,
                "details": []
            }
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Processing {len(products)} products through PROFILE flow")
        logger.info(f"{'='*70}\n")
        
        results = {
            "total": len(products),
            "success": 0,
            "failed": 0,
            "partial": 0,
            "details": []
        }
        
        # Process each product
        for i, product in enumerate(products, 1):
            logger.info(f"\n[{i}/{len(products)}] Processing product {product['id']}...")
            
            # Run PROFILE flow
            flow_result = await self.run_profile_flow(product)
            
            # Track result
            if flow_result.status == "success":
                if flow_result.fields_extracted == 3:
                    results["success"] += 1
                else:
                    results["partial"] += 1
            else:
                results["failed"] += 1
            
            results["details"].append({
                "product_id": flow_result.product_id,
                "submission_number": flow_result.submission_number,
                "status": flow_result.status,
                "fields_extracted": flow_result.fields_extracted,
                "device_description_length": len(flow_result.device_description) if flow_result.device_description else 0,
                "intended_use_length": len(flow_result.intended_use) if flow_result.intended_use else 0,
                "indications_for_use_length": len(flow_result.indications_for_use) if flow_result.indications_for_use else 0,
                "error": flow_result.error,
                "agents": flow_result.agents_executed,
                "timestamp": flow_result.timestamp
            })
            
            # Brief pause between products
            if i < len(products):
                await asyncio.sleep(0.5)
        
        logger.info(f"""
        
        {'='*70}
        ✅ PROFILE Processing Complete
        {'='*70}
        ├─ Total:   {results['total']}
        ├─ Success: {results['success']} (all 3 fields)
        ├─ Partial: {results['partial']} (1-2 fields)
        └─ Failed:  {results['failed']}
        {'='*70}
        """)
        
        return results


async def main():
    """CLI entry point for PROFILE service."""
    import sys
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Check for required environment variables
    exa_key = os.getenv("EXA_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not exa_key:
        logger.error("EXA_API_KEY environment variable not set (required for FDA search)")
        sys.exit(1)
    
    if not openai_key:
        logger.error("OPENAI_API_KEY environment variable not set (required for GPT-4o)")
        sys.exit(1)
    
    logger.info("✓ All required environment variables set")
    
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
    service = ProfileService(db_url)
    
    try:
        await service.initialize()
        results = await service.process_products(product_ids, limit)
        
        # Log results to database
        async with service.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO public.system_log (event, context)
                VALUES ($1, $2)
                """,
                "PROFILE_BATCH_COMPLETE",
                json.dumps(results)
            )
        
        sys.exit(0 if results["failed"] == 0 else 1)
    
    finally:
        await service.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
