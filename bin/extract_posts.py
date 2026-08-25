#!/usr/bin/env python3
"""
Extract Posts CLI

Extract entities (posts, patterns, orgs, guests) from web content.

Usage:
    extract-posts <url> [--dry-run] [--json] [--verbose]

Examples:
    extract-posts https://example.substack.com/p/post-title
    extract-posts https://example.substack.com/p/post-title --dry-run --json
    extract-posts https://example.substack.com/p/post-title --verbose
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, Optional

import asyncpg

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pitboss.agents import agent_request_to_extract_entities, agent_verify_upsert
from pitboss.context_builder import ContextBuilder
from pitboss.tools import ToolRegistry
from pitboss.config import get_config


# Configure logging
def setup_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s | %(message)s",
    )
    return logging.getLogger(__name__)


logger: Optional[logging.Logger] = None


def validate_url(url: str) -> str:
    """Validate and normalize URL."""
    url = (url or "").strip()
    
    if not url:
        raise ValueError("URL is empty")
    
    # Normalize: add https:// if no scheme
    if "://" not in url:
        url = f"https://{url}"
    
    # Basic validation
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL scheme: {url}")
    
    if " " in url:
        raise ValueError(f"URL contains spaces: {url}")
    
    return url


async def create_db_pool(database_url: str) -> asyncpg.Pool:
    """Create asyncpg connection pool from DATABASE_URL."""
    try:
        pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )
        logger.debug(f"✅ Database pool created")
        return pool
    except Exception as e:
        raise RuntimeError(f"Failed to connect to database: {e}") from e


async def extract_and_validate(
    db_pool: asyncpg.Pool,
    url: str,
    ctx_builder: ContextBuilder,
    tool_registry: ToolRegistry,
) -> Dict[str, Any]:
    """
    Run extraction and validation agents.
    
    Returns:
        Dictionary with keys:
        - status: "success" or "error"
        - extracted_entities: extracted entity payload (if success)
        - summary: human-readable summary
        - error: error message (if status="error")
    """
    
    # Build message_body for agents
    message_body: Dict[str, Any] = {
        "raw_text": f"extract {url}",
        "url": url,
        "_ctx": ctx_builder,
        "_tools": tool_registry,
        "_verb": "CONTENT",
        "session_id": "cli-extract",
        "request_id": "cli-extract-001",
    }
    
    logger.info(f"🔍 Extracting entities from {url}...")
    
    # Step 1: Extract entities via LLM
    try:
        decision, confidence, reason = await agent_request_to_extract_entities(message_body)
        logger.debug(f"  agent_request_to_extract_entities: decision={decision}, confidence={confidence:.2f}")
        logger.debug(f"  Reason: {reason}")
        
        if decision != "yes":
            return {
                "status": "error",
                "error": f"Extraction failed: {reason}",
                "extracted_entities": None,
                "summary": None,
            }
    except Exception as e:
        logger.error(f"  ❌ Extraction crashed: {e}", exc_info=logger.isEnabledFor(logging.DEBUG))
        return {
            "status": "error",
            "error": f"Extraction crashed: {str(e)}",
            "extracted_entities": None,
            "summary": None,
        }
    
    extracted_entities = message_body.get("extracted_entities", {})
    if not extracted_entities:
        return {
            "status": "error",
            "error": "No entities extracted (empty payload)",
            "extracted_entities": None,
            "summary": None,
        }
    
    logger.info(f"✅ Extraction complete - validating payload...")
    
    # Step 2: Verify payload
    try:
        decision, confidence, reason = await agent_verify_upsert(message_body)
        logger.debug(f"  agent_verify_upsert: decision={decision}, confidence={confidence:.2f}")
        
        if decision != "yes":
            logger.error(f"  ❌ Validation failed: {reason}")
            return {
                "status": "error",
                "error": f"Validation failed: {reason}",
                "extracted_entities": None,
                "summary": None,
            }
    except Exception as e:
        logger.error(f"  ❌ Validation crashed: {e}", exc_info=logger.isEnabledFor(logging.DEBUG))
        return {
            "status": "error",
            "error": f"Validation crashed: {str(e)}",
            "extracted_entities": None,
            "summary": None,
        }
    
    logger.info(f"✅ Validation passed")
    
    # Build summary
    summary = _build_summary(extracted_entities)
    
    return {
        "status": "success",
        "extracted_entities": extracted_entities,
        "summary": summary,
        "error": None,
    }


def _build_summary(extracted_entities: Dict[str, Any]) -> str:
    """Build human-readable summary from extracted entities."""
    lines = []
    
    # Post info
    posts = extracted_entities.get("posts", [])
    if posts:
        first_post = posts[0]
        post_name = first_post.get("name", "Unknown")
        published_at = first_post.get("published_at", "Unknown date")
        lines.append(f"📰 Post: '{post_name}' ({published_at})")
    
    # Organizations
    orgs = extracted_entities.get("orgs", [])
    if orgs:
        org_names = ", ".join([o.get("name", "") for o in orgs if o.get("name")])
        lines.append(f"🏢 Organizations: {org_names}")
    
    # Guests
    guests = extracted_entities.get("guests", [])
    if guests:
        guest_names = ", ".join([g.get("name", "") for g in guests if g.get("name")])
        lines.append(f"👤 Guests: {guest_names}")
    
    # Patterns
    patterns = extracted_entities.get("patterns", [])
    if patterns:
        pattern_names = ", ".join([p.get("name", "") for p in patterns if p.get("name")])
        lines.append(f"🎯 Patterns: {pattern_names}")
    
    return "\n".join(lines) if lines else "Extraction complete (no entities found)"


async def main():
    parser = argparse.ArgumentParser(
        prog="extract-posts",
        description="Extract entities from web content and upsert to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  extract-posts https://example.substack.com/p/post-title
  extract-posts https://example.substack.com/p/post-title --dry-run --json
  extract-posts https://example.substack.com/p/post-title --verbose
        """,
    )
    
    parser.add_argument(
        "url",
        help="URL to extract content from",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate extraction without upserting to database",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of summary",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    global logger
    logger = setup_logging(args.verbose)
    
    # Validate environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("❌ DATABASE_URL not set")
        return 3
    
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("❌ OPENAI_API_KEY not set")
        return 3
    
    # Validate and normalize URL
    try:
        url = validate_url(args.url)
        logger.debug(f"Normalized URL: {url}")
    except ValueError as e:
        logger.error(f"❌ Invalid URL: {e}")
        return 1
    
    # Connect to database
    db_pool = None
    try:
        db_pool = await create_db_pool(database_url)
    except RuntimeError as e:
        logger.error(f"❌ {e}")
        return 3
    
    try:
        # Initialize backend components
        logger.debug("Initializing context builder and tool registry...")
        config = get_config()
        ctx_builder = ContextBuilder(db_pool)
        tool_registry = ToolRegistry(db_pool, config)
        
        # Extract and validate
        result = await extract_and_validate(
            db_pool=db_pool,
            url=url,
            ctx_builder=ctx_builder,
            tool_registry=tool_registry,
        )
        
        if result["status"] == "error":
            logger.error(f"❌ {result['error']}")
            return 2
        
        extracted_entities = result["extracted_entities"]
        summary = result["summary"]
        
        # Upsert to database (unless --dry-run)
        if args.dry_run:
            logger.info("🔒 --dry-run mode: validation passed, skipping database upsert")
        else:
            logger.info("💾 Upserting entities to database...")
            try:
                upsert_res = await tool_registry.execute(
                    "execute_upsert",
                    jsonb_payload=extracted_entities,
                )
                
                if upsert_res["status"] != "success":
                    logger.error(f"❌ Upsert failed: {upsert_res.get('error')}")
                    return 3
                
                logger.info(f"✅ {upsert_res.get('message', 'Upsert complete')}")
            except Exception as e:
                logger.error(f"❌ Upsert crashed: {e}", exc_info=logger.isEnabledFor(logging.DEBUG))
                return 3
        
        # Output
        if args.json:
            output = {
                "status": "success",
                "url": url,
                "dry_run": args.dry_run,
                "entities": extracted_entities,
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(f"\n✅ Success!\n\n{summary}\n")
        
        return 0
    
    finally:
        if db_pool:
            await db_pool.close()
            logger.debug("Database pool closed")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
