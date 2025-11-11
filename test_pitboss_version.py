#!/usr/bin/env python
"""
Test which Pitboss version is being used based on current configuration.
"""

import os
import sys
from pathlib import Path

# Setup path
sys.path.append(str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv()

print("\n" + "="*60)
print("PITBOSS VERSION TEST")
print("="*60)

# Show current environment settings
print("\nEnvironment Variables:")
print(f"  PITBOSS_STRATEGY: {os.getenv('PITBOSS_STRATEGY', 'not set')}")
print(f"  GPT5_MINI_AVAILABLE: {os.getenv('GPT5_MINI_AVAILABLE', 'not set')}")
print(f"  PREFER_FLEXIBILITY: {os.getenv('PREFER_FLEXIBILITY', 'not set')}")

# Test the configuration
from services.config_advanced import AdvancedConfig

config = AdvancedConfig()

print(f"\nActive Configuration:")
print(f"  Strategy: {config.active_strategy.value}")
print(f"  Models: {config._get_active_models()}")

# Test what Pitboss will be created
print(f"\nTesting Pitboss Creation:")

import duckdb
db_location = os.path.expanduser(os.getenv("DATABASE_LOCATION", "~/code/data-review-database/datareview"))

try:
    db = duckdb.connect(db_location)
    pitboss = config.create_pitboss(db, None)
    
    print(f"  Pitboss Class: {pitboss.__class__.__name__}")
    print(f"  Module: {pitboss.__class__.__module__}")
    
    if pitboss.__class__.__module__ == "services.pitboss_llm_supervisor":
        print("\n✅ SUCCESS: Using LLM-supervised Pitboss with gpt-4o-mini!")
        print("   The LLM will orchestrate tool execution via function calling.")
    elif pitboss.__class__.__module__ == "services.pitboss_supervisor":
        print("\n✅ Using traditional Python-supervised Pitboss")
        print("   Python code orchestrates, GPT-4o generates SQL only.")
    elif pitboss.__class__.__module__ == "services.pitboss":
        print("\n⚠️  WARNING: Still using original pitboss.py")
        print("   The new refactored code is NOT being used.")
    else:
        print(f"\n❓ Unknown module: {pitboss.__class__.__module__}")
    
    db.close()
    
except Exception as e:
    print(f"\n❌ Error creating Pitboss: {e}")

print("\n" + "="*60)

# Instructions
if config.active_strategy.value == "llm_supervised":
    print("\n🎉 Your system is configured for LLM supervision!")
    print("\nWhen you run 'python -m services.run' and use the API,")
    print("gpt-4o-mini will orchestrate all tool execution.")
else:
    print("\n💡 To enable LLM supervision, ensure your .env has:")
    print("   PITBOSS_STRATEGY=llm_supervised")
    print("   GPT5_MINI_AVAILABLE=true")

print("\nNOTE: You must restart 'python -m services.run' for changes to take effect!")
print("="*60)