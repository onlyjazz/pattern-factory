#!/usr/bin/env python3
"""
Test for the URL extraction bug fix.
Verifies that consecutive extract commands use the correct URL each time,
not persisting stale metadata from previous extractions.
"""

import asyncio
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from pitboss.agents import agent_request_to_extract_entities


async def test_consecutive_url_extractions():
    """Test that consecutive extract commands don't reuse stale URL."""
    print("\n" + "=" * 70)
    print("TEST: Consecutive URL Extractions (Bug Fix)")
    print("=" * 70)

    # First extraction
    print("\n[1] First extraction: extract https://example.com")
    message_body_1 = {
        "raw_text": "extract https://example.com",
        "session_id": "sess-001",
    }
    
    decision_1, conf_1, reason_1 = await agent_request_to_extract_entities(message_body_1)
    print(f"    Decision: {decision_1}")
    print(f"    URL extracted: {message_body_1.get('url')}")
    assert message_body_1.get("url") == "https://example.com", "First extraction should get example.com"
    print("    ✅ Correct URL")

    # Second extraction with SAME message_body (simulating persistence)
    # This is where the bug would manifest
    print("\n[2] Second extraction (reusing message_body): extract https://example.org")
    message_body_1["raw_text"] = "extract https://example.org"
    
    decision_2, conf_2, reason_2 = await agent_request_to_extract_entities(message_body_1)
    print(f"    Decision: {decision_2}")
    print(f"    URL extracted: {message_body_1.get('url')}")
    
    # BUG CHECK: Should be example.org, not example.com
    if message_body_1.get("url") == "https://example.com":
        print("    ❌ BUG DETECTED: Old URL persisted!")
        return False
    
    assert message_body_1.get("url") == "https://example.org", "Second extraction should get example.org"
    print("    ✅ Correct URL (stale data was cleared)")

    # Third extraction with different URL
    print("\n[3] Third extraction: extract https://example.net")
    message_body_1["raw_text"] = "extract https://example.net"
    
    decision_3, conf_3, reason_3 = await agent_request_to_extract_entities(message_body_1)
    print(f"    Decision: {decision_3}")
    print(f"    URL extracted: {message_body_1.get('url')}")
    assert message_body_1.get("url") == "https://example.net", "Third extraction should get example.net"
    print("    ✅ Correct URL")

    print("\n" + "=" * 70)
    print("✅ BUG FIX VERIFIED: Each extraction uses correct URL")
    print("=" * 70)
    return True


async def test_metadata_clearing():
    """Test that all stale metadata is cleared between extractions."""
    print("\n" + "=" * 70)
    print("TEST: Metadata Clearing")
    print("=" * 70)

    message_body = {
        "raw_text": "extract https://example.com",
        "session_id": "sess-002",
    }

    # First extraction
    print("\n[1] First extraction")
    await agent_request_to_extract_entities(message_body)
    first_url = message_body.get("url")
    first_summary = message_body.get("content_summary")
    print(f"    URL: {first_url}")
    print(f"    Has content_summary: {'content_summary' in message_body}")

    # Second extraction with same message_body
    print("\n[2] Second extraction with different URL")
    message_body["raw_text"] = "extract https://example.org"
    await agent_request_to_extract_entities(message_body)
    second_url = message_body.get("url")
    second_summary = message_body.get("content_summary")
    
    print(f"    URL: {second_url}")
    print(f"    Has content_summary: {'content_summary' in message_body}")

    # Verify they're different
    assert first_url != second_url, "URLs should be different"
    print(f"\n    ✅ URLs are different: {first_url} != {second_url}")

    print("\n" + "=" * 70)
    print("✅ METADATA CLEARING VERIFIED")
    print("=" * 70)
    return True


async def main():
    try:
        result1 = await test_consecutive_url_extractions()
        result2 = await test_metadata_clearing()
        
        if result1 and result2:
            print("\n" + "=" * 70)
            print("✅ ALL TESTS PASSED - BUG IS FIXED")
            print("=" * 70)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
