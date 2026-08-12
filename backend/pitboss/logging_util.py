"""
Shared logging utilities for all agents.

Provides a single consistent interface for logging agent execution results
to the system_log table, eliminating code duplication across agents.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def log_event(
    db,
    event: str,
    context: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Log an event to system_log table.
    
    Args:
        db: Database connection (asyncpg pool or connection)
        event: Event name (e.g., "FEELGOOD_COMPLETE", "PROFILE_COMPLETE")
        context: Optional context dict with event details
    
    Returns:
        True if successful, False otherwise
    """
    if not db:
        logger.error("No database connection provided to log_event")
        return False
    
    try:
        context_json = json.dumps(context or {})
        
        # Insert into system_log using actual schema: (event, context)
        await db.execute(
            """
            INSERT INTO public.system_log (event, context)
            VALUES ($1, $2)
            """,
            event,
            context_json
        )
        
        logger.info(f"✓ Logged event: {event}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to log event '{event}': {e}", exc_info=True)
        return False
