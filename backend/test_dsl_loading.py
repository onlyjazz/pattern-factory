#!/usr/bin/env python3
"""
Test script to verify that the DSL (pattern-factory.yaml) loads correctly
from the ContextBuilder, regardless of the working directory.
"""

import sys
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pitboss.context_builder import ContextBuilder

def test_dsl_loading():
    """Test that DSL loads correctly."""
    logger.info("=" * 70)
    logger.info("Testing DSL Loading (pattern-factory.yaml)")
    logger.info("=" * 70)
    
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Script location: {os.path.abspath(__file__)}")
    
    try:
        # Create context builder (will load DSL automatically)
        builder = ContextBuilder(db_connection=None)
        
        logger.info("\n✅ DSL loaded successfully!")
        logger.info(f"DSL path: {builder.rules_yaml_path}")
        
        # Verify we have data
        if builder.yaml_data:
            system = builder.yaml_data.get("SYSTEM", {})
            data = builder.yaml_data.get("DATA", {})
            rules = builder.yaml_data.get("RULES", [])
            
            logger.info(f"\nDSL Content Summary:")
            logger.info(f"  - SYSTEM sections: {list(system.keys())}")
            logger.info(f"  - SYSTEM.prompt length: {len(system.get('prompt', ''))}")
            logger.info(f"  - DATA.tables: {len(data.get('tables', {}))}")
            logger.info(f"  - Available tables: {list(data.get('tables', {}).keys())[:5]}... ({len(data.get('tables', {}))} total)")
            logger.info(f"  - RULES defined: {len(rules)}")
            if rules:
                logger.info(f"  - First rule: {rules[0].get('name', 'N/A')}")
            
            # Test context building
            logger.info(f"\n✅ Testing context building...")
            context = builder.build_context(rule_code="Find all patterns")
            logger.info(f"  - System prompt length: {len(context['system'])} chars")
            logger.info(f"  - User prompt: '{context['user']}'")
            
            logger.info("\n" + "=" * 70)
            logger.info("✅ All tests passed!")
            logger.info("=" * 70)
            return True
        else:
            logger.error("❌ DSL loaded but appears empty!")
            return False
            
    except Exception as e:
        logger.error(f"\n❌ Failed to load DSL: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dsl_loading()
    sys.exit(0 if success else 1)
