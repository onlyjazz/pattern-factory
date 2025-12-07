#!/usr/bin/env python3
"""
Test JSON output with Substack-like HTML structure.
Demonstrates the content_summary JSON that will be sent to HITL.
"""

import asyncio
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from pitboss.agents import (
    _extract_post_title_and_subtitle,
    _extract_published_date,
    _heuristic_keywords,
)


def test_json_structure():
    """Test the complete JSON structure that will be returned to human."""
    print("\n" + "=" * 70)
    print("TEST: JSON Structure for HITL Review")
    print("=" * 70)

    # Simulated Substack HTML
    html = '''
    <html>
    <head><title>Example Post</title></head>
    <body>
    <h1 dir="auto" class="post-title published title-X77sOw">
        The Great Brain Bet: How Human-derived mini-brains and AI could upend big pharma
    </h1>
    <h3 dir="auto" class="subtitle subtitle-HEEcLo">
        Choosing powers in early stage TechBio
    </h3>
    <div class="pencraft pc-reset color-pub-secondary-text-hGQ02T line-height-20-t4M0El font-meta-MWBumP size-11-NuY2Zx weight-medium-fw81nC transform-uppercase-yKDgcq reset-IxiVJZ meta-EgzBVA">
        Oct 24, 2025
    </div>
    <p>Some content here about the topic...</p>
    </body>
    </html>
    '''

    # Extract fields
    title, subtitle = _extract_post_title_and_subtitle(html)
    published = _extract_published_date(html)
    keywords = _heuristic_keywords(title, subtitle)

    # Build content_summary
    url = "https://substack.com/article"
    content_summary = {
        "name": title,
        "description": subtitle,
        "keywords": keywords,
        "content_url": url,
        "content_source": "substack",
        "published_at": published,
    }

    print("\n📋 Extracted Fields:")
    print(f"  Title: {title}")
    print(f"  Subtitle: {subtitle}")
    print(f"  Published: {published}")
    print(f"  Keywords: {keywords}")

    print("\n📄 JSON Structure for HITL (reason field):")
    json_str = json.dumps(content_summary, ensure_ascii=False, indent=2)
    print(json_str)

    print("\n✅ Validating structure...")
    assert content_summary["name"] == title
    assert content_summary["description"] == subtitle
    assert content_summary["content_source"] == "substack"
    assert content_summary["published_at"] == "Oct 24, 2025"
    assert len(content_summary["keywords"]) > 0
    assert "content_url" in content_summary
    
    print("✅ All assertions passed!")
    print("\nThis JSON will be sent to frontend as the 'reason' field in the NO response.")
    print("Human can review and approve/modify before proceeding to model.verifyUpsert.")


async def main():
    try:
        test_json_structure()
        print("\n" + "=" * 70)
        print("✅ JSON OUTPUT TEST PASSED")
        print("=" * 70)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
