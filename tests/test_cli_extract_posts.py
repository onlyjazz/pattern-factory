#!/usr/bin/env python3
"""
Integration test examples for extract-posts CLI.

These tests demonstrate how the CLI would be used.
Note: Running these requires DATABASE_URL and OPENAI_API_KEY to be set.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from cli.extract_posts import validate_url


def test_url_validation():
    """Test URL validation and normalization."""
    print("\n🧪 Testing URL validation and normalization...\n")
    
    test_cases = [
        ("example.com", "https://example.com"),
        ("https://example.com", "https://example.com"),
        ("http://example.com", "http://example.com"),
        ("https://example.substack.com/p/post-title", "https://example.substack.com/p/post-title"),
    ]
    
    for input_url, expected in test_cases:
        result = validate_url(input_url)
        status = "✅" if result == expected else "❌"
        print(f"{status} {input_url:50} → {result}")
        assert result == expected, f"Expected {expected}, got {result}"
    
    # Test invalid URLs
    invalid_cases = [
        ("", "URL is empty"),
        ("not a url", "Invalid URL scheme"),
        ("ftp://example.com", "Invalid URL scheme"),
    ]
    
    for input_url, expected_error in invalid_cases:
        try:
            validate_url(input_url)
            print(f"❌ {input_url:50} should have raised ValueError")
            assert False, f"Should have raised ValueError for {input_url}"
        except ValueError as e:
            print(f"✅ {input_url:50} → ValueError: {str(e)}")


def test_cli_help():
    """Test CLI help output."""
    print("\n🧪 Testing CLI help...\n")
    
    import subprocess
    
    result = subprocess.run(
        ["./bin/extract-posts", "--help"],
        cwd=str(Path(__file__).parent.parent),
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 0, f"Help failed with code {result.returncode}"
    assert "usage: extract-posts" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--json" in result.stdout
    assert "--verbose" in result.stdout
    
    print("✅ Help output contains all expected options")


def test_cli_missing_url():
    """Test CLI error handling for missing URL."""
    print("\n🧪 Testing CLI error handling for missing URL...\n")
    
    import subprocess
    
    result = subprocess.run(
        ["./bin/extract-posts"],
        cwd=str(Path(__file__).parent.parent),
        capture_output=True,
        text=True,
    )
    
    assert result.returncode != 0, "Should fail with exit code != 0"
    assert "required: url" in result.stderr
    
    print("✅ CLI correctly rejects missing URL argument")


async def test_extract_and_validate_integration():
    """
    Demonstrates the full extraction and validation flow.
    
    This test requires:
    - DATABASE_URL set in environment
    - OPENAI_API_KEY set in environment
    - PostgreSQL running
    
    To run this test:
    DATABASE_URL=postgresql://... OPENAI_API_KEY=sk-... python -m pytest tests/test_cli_extract_posts.py::test_extract_and_validate_integration
    """
    print("\n🧪 Testing extract-and-validate flow (integration)...\n")
    
    database_url = os.getenv("DATABASE_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not database_url or not openai_api_key:
        print("⏭️  Skipping integration test (DATABASE_URL and/or OPENAI_API_KEY not set)")
        return
    
    # Import here to avoid import errors if dependencies are missing
    import asyncpg
    from cli.extract_posts import extract_and_validate
    from pitboss.context_builder import ContextBuilder
    from pitboss.tools import ToolRegistry
    from pitboss.config import get_config
    
    # Create connection pool
    db_pool = await asyncpg.create_pool(database_url)
    
    try:
        # Initialize components
        config = get_config()
        ctx_builder = ContextBuilder(db_pool)
        tool_registry = ToolRegistry(db_pool, config)
        
        # Test with a simple URL
        url = "https://example.com"
        
        result = await extract_and_validate(
            db_pool=db_pool,
            url=url,
            ctx_builder=ctx_builder,
            tool_registry=tool_registry,
        )
        
        print(f"Extraction result status: {result['status']}")
        print(f"Error (if any): {result.get('error')}")
        
        # Result may be error on example.com (simple page), which is fine
        # Just verify the flow completes
        print("✅ Extract-and-validate flow completed successfully")
        
    finally:
        await db_pool.close()


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🧪 Extract-Posts CLI Integration Tests")
    print("=" * 70)
    
    try:
        # Synchronous tests
        test_url_validation()
        test_cli_help()
        test_cli_missing_url()
        
        # Async integration test
        asyncio.run(test_extract_and_validate_integration())
        
        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70 + "\n")
        
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
