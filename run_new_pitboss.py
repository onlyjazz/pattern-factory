#!/usr/bin/env python
"""
Run New Pitboss with GPT-5-mini LLM Supervision

This script provides an easy way to test and use the new LLM-supervised
pitboss that uses GPT-5-mini with function calling for orchestration.

Usage:
    python run_new_pitboss.py                    # Interactive mode
    python run_new_pitboss.py --demo             # Run demonstration
    python run_new_pitboss.py --rule "ALT > 120" # Run single rule
    python run_new_pitboss.py --dsl clovis.yaml  # Run DSL file
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path
from typing import Optional
import yaml
import duckdb

# Setup path for imports
sys.path.append(str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_environment():
    """Check if environment is properly configured for GPT-5-mini."""
    
    print("\n🔍 Checking Environment Configuration...")
    print("-" * 50)
    
    # Check OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        print("✅ OpenAI API key found")
    else:
        print("❌ OpenAI API key not found in .env")
        return False
    
    # Check GPT-5-mini configuration
    gpt5_available = os.getenv("GPT5_MINI_AVAILABLE")
    strategy = os.getenv("PITBOSS_STRATEGY")
    
    if gpt5_available == "true":
        print("✅ GPT-5-mini enabled")
    else:
        print("⚠️  GPT-5-mini not enabled (set GPT5_MINI_AVAILABLE=true)")
    
    if strategy == "llm_supervised":
        print("✅ LLM-supervised strategy selected")
    elif strategy:
        print(f"ℹ️  Strategy set to: {strategy}")
    else:
        print("ℹ️  No strategy specified (will use auto-detection)")
    
    # Check database
    db_location = os.path.expanduser(os.getenv("DATABASE_LOCATION", ""))
    if os.path.exists(db_location):
        print(f"✅ Database found at: {db_location}")
    else:
        print(f"⚠️  Database not found at: {db_location}")
    
    print("-" * 50)
    return True


async def run_demonstration():
    """Run a demonstration of the LLM-supervised pitboss."""
    
    print("\n🎯 Running LLM-Supervised Pitboss Demonstration")
    print("=" * 60)
    
    # Import the LLM-supervised pitboss
    from services.pitboss_llm_supervisor import LLMSupervisedPitboss
    
    # Connect to database
    db_location = os.path.expanduser(os.getenv("DATABASE_LOCATION", "~/code/data-review-database/datareview"))
    db = duckdb.connect(db_location)
    
    # Create pitboss instance
    pitboss = LLMSupervisedPitboss(db, websocket=None, use_async=True)
    
    # Example DSL sections
    protocol_text = """
Protocol ID: DEMO-001
Title: Demonstration Clinical Trial
Eligibility:
  Inclusion:
    - Age >= 18 years
    - ALT <= 3x ULN at baseline
    """
    
    data_block = """
Available tables and columns:
- adsl_clovis: USUBJID, AGE, SEX, RACE
- adlb_clovis: USUBJID, ALT, AST, BILI, VISIT, LBDT
    """
    
    # Example rules
    rules = [
        {
            "rule_code": "ALT_HIGH",
            "logic": "Flag subjects with ALT > 3x ULN (120)",
            "severity": "major",
            "message": "Elevated ALT detected"
        },
        {
            "rule_code": "AGE_VIOLATION",
            "logic": "Flag subjects under 18 years old",
            "severity": "critical",
            "message": "Age eligibility violation"
        }
    ]
    
    print("\n📋 Protocol Context:")
    print(protocol_text)
    
    print("\n🗂️ Data Schema:")
    print(data_block)
    
    print("\n📜 Rules to Execute:")
    for rule in rules:
        print(f"  - {rule['rule_code']}: {rule['logic']}")
    
    print("\n" + "=" * 60)
    print("🚀 Executing Rules with GPT-5-mini Orchestration...")
    print("=" * 60)
    
    # Execute each rule
    for rule in rules:
        print(f"\n▶️  Processing {rule['rule_code']}...")
        
        rule_yaml = yaml.dump(rule)
        
        try:
            result = await pitboss.run_rule_fastpath(
                protocol_id="DEMO-001",
                protocol_text=protocol_text,
                data_block=data_block,
                dsl_rule_yaml=rule_yaml
            )
            
            if result["status"] == "success":
                print(f"✅ Success! Tool calls made:")
                for tool_call in result.get("tool_calls", []):
                    print(f"   - {tool_call['tool']}: {tool_call['result'].get('status')}")
                    if tool_call['tool'] == 'data_table':
                        row_count = tool_call['result'].get('row_count', 0)
                        table_name = tool_call['result'].get('table_name', '')
                        print(f"     Created table: {table_name} with {row_count} rows")
                
                if result.get("tokens_used"):
                    print(f"   Tokens used: {result['tokens_used']}")
            else:
                print(f"❌ Error: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print("\n" + "=" * 60)
    print("✨ Demonstration Complete!")
    
    # Show execution log
    log = pitboss.get_execution_log()
    if log:
        print(f"\n📊 Execution Log: {len(log)} entries")
        for entry in log[-3:]:  # Show last 3 entries
            print(f"  - {entry['tool']}: {entry['rule_code']} at {entry['timestamp']}")
    
    db.close()


async def run_single_rule(rule_text: str):
    """Run a single rule using the LLM-supervised pitboss."""
    
    print(f"\n🎯 Running Single Rule: {rule_text}")
    
    from services.pitboss_llm_supervisor import LLMSupervisedPitboss
    
    # Connect to database
    db_location = os.path.expanduser(os.getenv("DATABASE_LOCATION", "~/code/data-review-database/datareview"))
    db = duckdb.connect(db_location)
    
    # Create pitboss
    pitboss = LLMSupervisedPitboss(db, websocket=None, use_async=True)
    
    # Minimal context
    protocol_text = "Protocol: Clinical Trial"
    data_block = "Tables: adsl_clovis, adlb_clovis"
    rule_yaml = yaml.dump({
        "rule_code": "USER_RULE",
        "logic": rule_text,
        "severity": "major"
    })
    
    result = await pitboss.run_rule_fastpath(
        protocol_id="USER-001",
        protocol_text=protocol_text,
        data_block=data_block,
        dsl_rule_yaml=rule_yaml
    )
    
    if result["status"] == "success":
        print("✅ Rule executed successfully!")
        for tool_call in result.get("tool_calls", []):
            print(f"  - {tool_call['tool']}: {tool_call['result'].get('status')}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    db.close()


async def run_dsl_file(dsl_path: str):
    """Run all rules from a DSL file."""
    
    print(f"\n📄 Running DSL File: {dsl_path}")
    
    if not os.path.exists(dsl_path):
        print(f"❌ File not found: {dsl_path}")
        return
    
    from services.pitboss_llm_supervisor import LLMSupervisedPitboss
    
    # Load DSL
    with open(dsl_path, 'r') as f:
        dsl_text = f.read()
    
    # Connect to database
    db_location = os.path.expanduser(os.getenv("DATABASE_LOCATION", "~/code/data-review-database/datareview"))
    db = duckdb.connect(db_location)
    
    # Create pitboss
    pitboss = LLMSupervisedPitboss(db, websocket=None, use_async=True)
    
    # Parse DSL to get protocol_id
    try:
        dsl = yaml.safe_load(dsl_text)
        protocol_id = dsl.get('PROTOCOL', {}).get('id', 'UNKNOWN')
    except:
        protocol_id = 'UNKNOWN'
    
    # Run all rules
    result = await pitboss.run_all_rules(protocol_id, dsl_text)
    
    if result["status"] == "success":
        print(f"✅ Executed {result['rules_executed']} rules successfully!")
        for rule_result in result.get("results", []):
            rule_code = rule_result["rule_code"]
            status = rule_result["result"]["status"]
            print(f"  - {rule_code}: {status}")
    else:
        print(f"❌ Error: {result.get('error')}")
    
    db.close()


async def interactive_mode():
    """Interactive mode for testing rules."""
    
    print("\n🤖 Interactive LLM-Supervised Pitboss")
    print("=" * 60)
    print("Using GPT-5-mini with function calling for orchestration")
    print("Type 'help' for commands, 'exit' to quit")
    print("=" * 60)
    
    from services.pitboss_llm_supervisor import LLMSupervisedPitboss
    
    # Connect to database
    db_location = os.path.expanduser(os.getenv("DATABASE_LOCATION", "~/code/data-review-database/datareview"))
    db = duckdb.connect(db_location)
    
    # Create pitboss
    pitboss = LLMSupervisedPitboss(db, websocket=None, use_async=True)
    
    while True:
        try:
            command = input("\n> ").strip()
            
            if command.lower() == 'exit':
                break
            elif command.lower() == 'help':
                print("""
Commands:
  rule <text>  - Execute a rule (e.g., rule ALT > 120)
  status       - Show current configuration
  demo         - Run demonstration
  clear        - Clear screen
  exit         - Exit interactive mode
                """)
            elif command.lower() == 'status':
                print(f"Strategy: {os.getenv('PITBOSS_STRATEGY', 'auto')}")
                print(f"GPT-5-mini: {os.getenv('GPT5_MINI_AVAILABLE', 'false')}")
                print(f"Database: Connected")
            elif command.lower() == 'demo':
                await run_demonstration()
            elif command.lower() == 'clear':
                os.system('clear' if os.name == 'posix' else 'cls')
            elif command.startswith('rule '):
                rule_text = command[5:].strip()
                if rule_text:
                    await run_single_rule(rule_text)
                else:
                    print("Please provide rule text")
            else:
                print(f"Unknown command: {command}")
                print("Type 'help' for available commands")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    db.close()
    print("\n👋 Goodbye!")


def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(
        description="Run the new LLM-supervised Pitboss with GPT-5-mini"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demonstration"
    )
    parser.add_argument(
        "--rule",
        type=str,
        help="Execute a single rule"
    )
    parser.add_argument(
        "--dsl",
        type=str,
        help="Path to DSL file to execute"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check environment configuration only"
    )
    
    args = parser.parse_args()
    
    # Always check environment first
    if not check_environment():
        if not args.check:
            print("\n⚠️  Environment check failed. Fix issues above and try again.")
        return
    
    if args.check:
        print("\n✅ Environment is properly configured!")
        return
    
    # Determine what to run
    if args.demo:
        asyncio.run(run_demonstration())
    elif args.rule:
        asyncio.run(run_single_rule(args.rule))
    elif args.dsl:
        asyncio.run(run_dsl_file(args.dsl))
    else:
        # Interactive mode
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()