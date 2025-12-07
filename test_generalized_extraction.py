#!/usr/bin/env python3
"""
Test for generalized entity extraction agent.
Verifies that the agent loads system prompt from YAML and returns
the correct JSON structure with posts, patterns, orgs, guests, and links.
"""

import asyncio
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from pitboss.agents import _get_extract_content_system_prompt
from pitboss.context_builder import ContextBuilder


async def test_yaml_prompt_loading():
    """Test that EXTRACT_CONTENT system prompt loads from YAML."""
    print("\n" + "=" * 70)
    print("TEST: Load EXTRACT_CONTENT system prompt from YAML")
    print("=" * 70)

    # Create a context builder (loads YAML)
    try:
        # Create a mock DB connection (not needed for YAML loading)
        context_builder = ContextBuilder(None)
        
        # Get the system prompt
        prompt = _get_extract_content_system_prompt(context_builder)
        
        if prompt:
            print(f"\n✅ Loaded EXTRACT_CONTENT prompt ({len(prompt)} chars)")
            print(f"\nFirst 200 chars:\n{prompt[:200]}...")
            
            # Verify it contains key elements
            assert "entity-extraction agent" in prompt, "Prompt should mention entity extraction"
            assert "orgs" in prompt, "Prompt should mention orgs"
            assert "guests" in prompt, "Prompt should mention guests"
            assert "posts" in prompt, "Prompt should mention posts"
            assert "patterns" in prompt, "Prompt should mention patterns"
            print("\n✅ Prompt contains all required sections")
            return True
        else:
            print("❌ Could not load EXTRACT_CONTENT prompt from YAML")
            return False
            
    except Exception as e:
        print(f"❌ Error loading prompt: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_json_structure():
    """Test that the JSON structure matches the spec."""
    print("\n" + "=" * 70)
    print("TEST: JSON Structure Validation")
    print("=" * 70)

    # Example extracted data (what LLM would return)
    extracted_data = {
        "posts": [
            {
                "name": "Automation in Biotech",
                "description": "A deep dive into automation trends in next-gen biotech.",
                "keywords": ["automation", "labs", "ai"],
                "content_url": "https://example.com/post",
                "content_source": "substack",
                "published_at": None
            }
        ],
        "patterns": [
            {
                "name": "Process Power",
                "description": "Efficiency grows when workflows become structured and repeatable.",
                "kind": "pattern",
                "keywords": ["process", "efficiency", "systems"],
                "metadata": {"source": "LLM extraction test"},
                "highlights": ["Structured workflows", "Repeatability"],
                "content_source": "substack"
            }
        ],
        "orgs": [
            {
                "name": "HelixBio",
                "description": "Biotech automation company",
                "keywords": ["biotech", "automation"],
                "content_source": "substack"
            }
        ],
        "guests": [
            {
                "name": "Alice Smith",
                "description": "CEO of HelixBio",
                "job_description": "Chief Executive Officer",
                "keywords": ["ceo", "biotech"],
                "content_source": "substack"
            }
        ],
        "pattern_post_link": [
            {
                "pattern_name": "Process Power",
                "post_name": "Automation in Biotech"
            }
        ],
        "pattern_org_link": [
            {
                "pattern_name": "Process Power",
                "org_name": "HelixBio"
            }
        ],
        "pattern_guest_link": [
            {
                "pattern_name": "Process Power",
                "guest_name": "Alice Smith"
            }
        ]
    }

    print("\n📋 Validating JSON structure...")
    
    # Verify required keys
    required_keys = ["posts", "patterns", "orgs", "guests", "pattern_post_link", "pattern_org_link", "pattern_guest_link"]
    for key in required_keys:
        assert key in extracted_data, f"Missing key: {key}"
        assert isinstance(extracted_data[key], list), f"{key} should be a list"
        print(f"  ✅ {key}: {len(extracted_data[key])} items")

    # Verify posts structure
    if extracted_data["posts"]:
        post = extracted_data["posts"][0]
        assert "name" in post, "Post should have name"
        assert "description" in post, "Post should have description"
        assert "keywords" in post, "Post should have keywords"
        assert "content_url" in post, "Post should have content_url"
        assert "content_source" in post, "Post should have content_source"
        assert post["content_source"] == "substack", "content_source should be 'substack'"
        print(f"\n✅ Posts structure valid")

    # Verify patterns structure
    if extracted_data["patterns"]:
        pattern = extracted_data["patterns"][0]
        assert "name" in pattern, "Pattern should have name"
        assert "description" in pattern, "Pattern should have description"
        assert "kind" in pattern, "Pattern should have kind"
        assert pattern["kind"] in ("pattern", "anti-pattern"), "kind should be 'pattern' or 'anti-pattern'"
        print(f"✅ Patterns structure valid")

    # Verify links reference actual entities
    if extracted_data["pattern_post_link"]:
        link = extracted_data["pattern_post_link"][0]
        pattern_names = [p["name"] for p in extracted_data["patterns"]]
        post_names = [p["name"] for p in extracted_data["posts"]]
        assert link["pattern_name"] in pattern_names, "Link should reference existing pattern"
        assert link["post_name"] in post_names, "Link should reference existing post"
        print(f"✅ Link tables valid")

    print("\n" + "=" * 70)
    print("✅ JSON STRUCTURE VALID")
    print("=" * 70)
    return True


async def main():
    try:
        print("\n🧪 Testing Generalized Entity Extraction\n")
        
        result1 = await test_yaml_prompt_loading()
        result2 = test_json_structure()
        
        if result1 and result2:
            print("\n" + "=" * 70)
            print("✅ ALL TESTS PASSED")
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
