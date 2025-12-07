#!/usr/bin/env python3
"""
Test script for extract content flow.
Tests model.requestToExtractEntities agent in isolation.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from pitboss.agents import (
    agent_capo_content,
    agent_verify_request_content,
    agent_request_to_extract_entities,
    _extract_post_title_and_subtitle,
    _extract_published_date,
    _heuristic_keywords,
)
import json


async def test_extract_url():
    """Test the extract flow with a simple URL."""
    print("\n" + "=" * 70)
    print("TEST: Extract flow with 'extract https://example.com'")
    print("=" * 70)

    # Simulate user input
    message_body = {
        "raw_text": "extract https://example.com",
        "session_id": "sess-test-001",
        "request_id": "req-test-001",
    }

    # Step 1: model.Capo (CONTENT flow)
    print("\n[1] model.Capo (CONTENT flow)")
    decision, confidence, reason = await agent_capo_content(message_body)
    print(f"    Decision: {decision}")
    print(f"    Confidence: {confidence:.2f}")
    print(f"    Reason: {reason}")
    assert decision == "yes", "Capo should accept 'extract' command"

    # Step 2: model.verifyRequest (CONTENT flow)
    print("\n[2] model.verifyRequest (CONTENT flow)")
    decision, confidence, reason = await agent_verify_request_content(message_body)
    print(f"    Decision: {decision}")
    print(f"    Confidence: {confidence:.2f}")
    print(f"    Reason: {reason}")
    assert decision == "yes", "verifyRequest should find URL"

    # Step 3: model.requestToExtractEntities
    print("\n[3] model.requestToExtractEntities")
    print("    (Fetching URL and extracting post metadata...)")
    decision, confidence, reason = await agent_request_to_extract_entities(message_body)
    print(f"    Decision: {decision}")
    print(f"    Confidence: {confidence:.2f}")
    print(f"    Reason:\n{reason}")
    
    # Check that metadata was stored
    print(f"\n    URL in message_body: {message_body.get('url')}")
    print(f"    HTTP status: {message_body.get('http_status')}")
    print(f"    Content preview (first 80 chars): {message_body.get('content_preview')}")
    print(f"    Post title: {message_body.get('post_title')}")
    print(f"    Post subtitle: {message_body.get('post_subtitle')}")
    print(f"    Published at: {message_body.get('published_at')}")
    print(f"    Content summary:")
    if "content_summary" in message_body:
        print(f"      {json.dumps(message_body['content_summary'], indent=8)}")
    
    # Should return "no" for HITL (human review of extracted fields)
    assert decision == "no", "Should return 'no' for HITL with extracted metadata"
    
    # Verify JSON has required structure
    if "content_summary" in message_body:
        cs = message_body["content_summary"]
        assert "name" in cs
        assert "description" in cs
        assert "keywords" in cs
        assert "content_url" in cs
        assert "content_source" in cs
        assert cs["content_source"] == "substack"
        assert "published_at" in cs
    
    print("\n✅ Test passed!")


async def test_extract_no_url():
    """Test the extract flow without a URL."""
    print("\n" + "=" * 70)
    print("TEST: Extract flow without URL")
    print("=" * 70)

    message_body = {
        "raw_text": "extract",
        "session_id": "sess-test-002",
        "request_id": "req-test-002",
    }

    # Step 1: model.Capo
    print("\n[1] model.Capo (CONTENT flow)")
    decision, confidence, reason = await agent_capo_content(message_body)
    print(f"    Decision: {decision}")
    print(f"    Reason: {reason}")

    # Step 2: model.verifyRequest
    print("\n[2] model.verifyRequest (CONTENT flow)")
    decision, confidence, reason = await agent_verify_request_content(message_body)
    print(f"    Decision: {decision}")
    print(f"    Reason: {reason}")
    assert decision == "no", "Should ask for URL"

    print("\n✅ Test passed!")


async def test_extract_invalid_url():
    """Test with invalid URL."""
    print("\n" + "=" * 70)
    print("TEST: Extract with invalid URL")
    print("=" * 70)

    message_body = {
        "raw_text": "extract not-a-url",
        "session_id": "sess-test-003",
        "request_id": "req-test-003",
    }

    print("\n[1] model.requestToExtractEntities")
    decision, confidence, reason = await agent_request_to_extract_entities(message_body)
    print(f"    Decision: {decision}")
    print(f"    Reason: {reason}")
    assert decision == "no", "Should reject invalid URL"

    print("\n✅ Test passed!")


def test_title_subtitle_extraction():
    """Test the HTML title and subtitle extraction helper."""
    print("\n" + "=" * 70)
    print("TEST: Extract title and subtitle from HTML")
    print("=" * 70)

    html = '''
    <h1 dir="auto" class="post-title published title-X77sOw">The Great Brain Bet: How Human-derived mini-brains and AI could upend big pharma</h1>
    <h3 dir="auto" class="subtitle subtitle-HEEcLo">Choosing powers in early stage TechBio</h3>
    <div class="pencraft pc-reset color-pub-secondary-text-hGQ02T line-height-20-t4M0El font-meta-MWBumP size-11-NuY2Zx weight-medium-fw81nC transform-uppercase-yKDgcq reset-IxiVJZ meta-EgzBVA">Oct 24, 2025</div>
    '''

    title, subtitle = _extract_post_title_and_subtitle(html)
    print(f"    Title: {title}")
    print(f"    Subtitle: {subtitle}")

    assert title == "The Great Brain Bet: How Human-derived mini-brains and AI could upend big pharma"
    assert subtitle == "Choosing powers in early stage TechBio"
    
    # Test date extraction
    date = _extract_published_date(html)
    print(f"    Published: {date}")
    assert date == "Oct 24, 2025"
    
    # Test heuristic keywords
    keywords = _heuristic_keywords(title, subtitle)
    print(f"    Keywords (heuristic): {keywords}")
    assert len(keywords) > 0
    
    print("\n✅ Test passed!")


async def main():
    print("\n🧪 Testing Extract Content Flow\n")
    
    try:
        test_title_subtitle_extraction()
        await test_extract_url()
        await test_extract_no_url()
        await test_extract_invalid_url()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
