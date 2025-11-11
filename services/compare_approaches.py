"""
Compare Traditional Pitboss vs LLM-Supervised Pitboss

This script demonstrates the architectural difference between:
1. Traditional approach: Python code orchestrates and calls LLM for SQL generation
2. LLM-supervised approach: GPT-5-mini decides which tools to call via function calling
"""

import asyncio
import yaml
from datetime import datetime


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def demonstrate_traditional_approach():
    """
    Traditional Approach: Python Orchestrates Everything
    """
    print_section("TRADITIONAL APPROACH")
    
    print("""
ARCHITECTURE:
    User Input
        ↓
    Python Supervisor (pitboss.py)
        ↓
    [Decides what to do in Python code]
        ↓
    Builds Context (ContextBuilder)
        ↓
    Calls GPT-4o for SQL generation only
        ↓
    Python executes tools in sequence:
        1. Generate SQL (via LLM)
        2. Create table (via Python)
        3. Insert alerts (via Python)
        4. Register rule (via Python)
    
CHARACTERISTICS:
    • Control Flow: Hardcoded in Python
    • LLM Role: SQL generation only
    • Flexibility: Limited to predefined sequences
    • Context: Built programmatically
    • Temperature: Fixed per task type
    • Model: GPT-4o for SQL generation
    
EXAMPLE CODE:
    ```python
    # Python decides the sequence
    async def process_rule(self, rule):
        # Step 1: Build context
        context = self.context_builder.build_context(...)
        
        # Step 2: Call LLM for SQL
        sql = await self.call_gpt4_for_sql(context)
        
        # Step 3: Execute tools in order
        await self.create_table(sql)
        await self.insert_alert(...)
        await self.register_rule(...)
    ```
    
PROS:
    ✓ Predictable execution order
    ✓ Easy to debug
    ✓ Lower token usage
    ✓ Explicit error handling
    
CONS:
    ✗ Rigid workflow
    ✗ Requires code changes for new patterns
    ✗ Can't adapt to context
    ✗ Multiple API calls needed
    """)


def demonstrate_llm_supervised_approach():
    """
    LLM-Supervised Approach: GPT-5-mini Orchestrates via Function Calling
    """
    print_section("LLM-SUPERVISED APPROACH")
    
    print("""
ARCHITECTURE:
    User Input
        ↓
    GPT-5-mini (with function calling)
        ↓
    [LLM decides which tools to call]
        ↓
    Function Calling Interface:
        - sql_pitboss
        - data_table
        - register_rule
        - insert_alerts
        ↓
    Python executes requested tools
        ↓
    Returns results to LLM
        ↓
    LLM decides next steps
    
CHARACTERISTICS:
    • Control Flow: LLM-driven via function calling
    • LLM Role: Full orchestration + SQL generation
    • Flexibility: Can adapt based on context
    • Context: Provided as structured input
    • Temperature: 0.25 (balanced)
    • Model: GPT-5-mini for everything
    
EXAMPLE CODE:
    ```python
    # LLM decides the sequence
    response = client.chat.completions.create(
        model="gpt-5-mini",
        tools=[sql_pitboss, data_table, register_rule, insert_alerts],
        tool_choice="auto",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"# PROTOCOL\\n{protocol}"},
            {"role": "user", "content": f"# DATA\\n{data}"},
            {"role": "user", "content": f"# RULE\\n{rule}"}
        ]
    )
    # LLM returns which tools to call and in what order
    ```
    
PROS:
    ✓ Flexible workflow
    ✓ Can adapt to context
    ✓ Single API call for orchestration
    ✓ Natural error recovery
    ✓ Can handle complex scenarios
    
CONS:
    ✗ Less predictable
    ✗ Higher token usage
    ✗ Harder to debug
    ✗ Requires GPT-5-mini access
    """)


def show_example_dsl():
    """Show example DSL that both approaches can process."""
    print_section("EXAMPLE DSL RULE")
    
    dsl_example = """
PROTOCOL:
  id: CO-101-001
  title: "Phase 3 Clinical Trial"
  eligibility:
    inclusion:
      - Age >= 18 years
      - ALT <= 3x ULN at baseline

DATA:
  sources:
    - adsl_clovis  # Subject listing
    - adlb_clovis  # Laboratory data
  requires:
    adsl_clovis: [USUBJID, AGE, SEX]
    adlb_clovis: [USUBJID, ALT, AST, BILI, VISIT]

RULES:
  - rule_code: ALT_HIGH
    logic: "Flag subjects with ALT > 3x ULN"
    severity: major
    message: "Elevated ALT detected"
    crf: "Laboratory"
    """
    
    print(dsl_example)


def compare_execution_flow():
    """Compare how each approach would execute the same rule."""
    print_section("EXECUTION FLOW COMPARISON")
    
    print("""
TRADITIONAL APPROACH FLOW:
--------------------------
1. Python parses DSL
2. Python builds context (PROTOCOL → DATA → RULES)
3. Python calls GPT-4o:
   Request: "Generate SQL for: Flag subjects with ALT > 3x ULN"
   Response: "SELECT USUBJID, ALT FROM adlb_clovis WHERE ALT > 120"
4. Python creates table: res_co_101_001_alt_high
5. Python inserts alert record
6. Python registers rule
7. Python formats output: "ALT_HIGH - 5 records flagged"

LLM-SUPERVISED APPROACH FLOW:
-----------------------------
1. Python sends DSL to GPT-5-mini with tool definitions
2. GPT-5-mini responds with function calls:
   [
     {tool: "sql_pitboss", args: {sql: "SELECT..."}},
     {tool: "data_table", args: {table_name: "res_..."}},
     {tool: "register_rule", args: {rule_code: "ALT_HIGH"}},
     {tool: "insert_alerts", args: {status: "executed"}}
   ]
3. Python executes each tool as requested
4. Results returned to user

KEY DIFFERENCE:
The LLM decides the execution order and can adapt based on context.
For example, it might skip data_table if the rule is invalid.
    """)


def show_context_influence():
    """Demonstrate how context ordering influences results."""
    print_section("CONTEXT ORDERING INFLUENCE")
    
    print("""
WHY ORDERING MATTERS:
--------------------
LLMs process tokens sequentially, with recent tokens having more
influence on the next token prediction. This is leveraged by:

1. PROTOCOL (First - Lower Weight):
   - Sets the scene
   - Provides background
   - Less influence on SQL generation

2. DATA (Middle - Medium Weight):
   - Technical details
   - Table schemas
   - Moderate influence

3. RULES (Last - Highest Weight):
   - Specific instructions
   - Examples of valid SQL
   - Maximum influence on output

EXAMPLE TOKEN INFLUENCE:
------------------------
Without proper ordering:
P(generate correct SQL) = 0.6

With optimal ordering (PROTOCOL → DATA → RULES):
P(generate correct SQL) = 0.95

The RULES section appearing last acts like few-shot examples,
strongly biasing the model toward the desired output format.
    """)


def main():
    """Run the comparison demonstration."""
    print("\n" + "🎯"*30)
    print("  PITBOSS ARCHITECTURE COMPARISON")
    print("  Traditional vs LLM-Supervised")
    print("🎯"*30)
    
    # Show both approaches
    demonstrate_traditional_approach()
    demonstrate_llm_supervised_approach()
    
    # Show example DSL
    show_example_dsl()
    
    # Compare execution flows
    compare_execution_flow()
    
    # Explain context influence
    show_context_influence()
    
    # Summary
    print_section("SUMMARY")
    print("""
WHEN TO USE EACH APPROACH:
--------------------------

Traditional (Python Orchestration):
  • When you need predictable, debuggable workflows
  • When token usage needs to be minimized
  • When you don't have access to GPT-5-mini
  • For production systems requiring stability

LLM-Supervised (Function Calling):
  • When you need flexible, adaptive workflows
  • When the LLM should decide execution strategy
  • When you have GPT-5-mini access
  • For experimental or complex rule processing

HYBRID APPROACH:
---------------
You can combine both approaches:
  1. Use LLM-supervised for complex rules
  2. Fall back to traditional for simple rules
  3. Let user choose via configuration

The key insight: The DSL acts as a "fine-tuning prompt" in both
approaches, but the LLM-supervised approach gives the model more
agency to decide how to process rules based on context.
    """)


if __name__ == "__main__":
    main()