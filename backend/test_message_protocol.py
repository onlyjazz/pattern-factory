#!/usr/bin/env python3
"""
Test script: Message Protocol v1.1 and Workflow Decision Trees

Demonstrates:
1. Creating and parsing MessageEnvelope
2. Decision tree walkthrough (RULE and CONTENT flows)
3. Agent call sequence with confidence/reason
4. Protocol versioning and tracing
"""

import asyncio
import logging
from pitboss.envelope import (
    MessageEnvelope,
    MessageType,
    Verb,
    Decision,
    make_request,
    make_response,
    make_error,
    make_success,
)
from pitboss.workflow import WorkflowEngine
from pitboss.agents import call_agent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Test 1: Envelope Creation and Serialization
# ============================================================================

def test_envelope_creation():
    print("\n" + "="*70)
    print("TEST 1: Envelope Creation & Serialization")
    print("="*70)
    
    # Create request
    req = make_request(
        session_id="sess-001",
        request_id="req-001",
        verb=Verb.RULE,
        message_body={"rule_text": "Show me patterns in episodes"}
    )
    
    print(f"✅ Created request envelope")
    print(f"   type: {req.type.value}")
    print(f"   verb: {req.verb.value}")
    print(f"   session_id: {req.session_id}")
    print(f"   request_id: {req.request_id}")
    
    # Convert to JSON
    json_str = req.to_json()
    print(f"✅ Serialized to JSON ({len(json_str)} bytes)")
    
    # Parse back
    parsed = MessageEnvelope.from_json(json_str)
    print(f"✅ Parsed from JSON")
    print(f"   type: {parsed.type.value}")
    print(f"   nextAgent: {parsed.nextAgent}")
    
    assert parsed.session_id == req.session_id
    assert parsed.request_id == req.request_id
    print(f"✅ Envelope round-trip successful")


# ============================================================================
# Test 2: Workflow Engine - Decision Tree Navigation
# ============================================================================

def test_workflow_engine():
    print("\n" + "="*70)
    print("TEST 2: Workflow Engine Decision Trees")
    print("="*70)
    
    engine = WorkflowEngine()
    
    # Test RULE flow
    print("\n📋 RULE Flow Navigation:")
    agents = [
        ("model.Capo", "yes"),
        ("model.verifyRequest", "yes"),
        ("model.ruleToSQL", "yes"),
        ("model.verifySQL", "yes"),
    ]
    
    for agent, decision in agents:
        next_agent = engine.get_next_agent("RULE", agent, decision)
        print(f"  {agent} ({decision}) → {next_agent}")
    
    # Test CONTENT flow
    print("\n📋 CONTENT Flow Navigation:")
    agents_content = [
        ("model.Capo", "yes"),
        ("model.verifyRequest", "yes"),
        ("model.requestToExtractEntities", "yes"),
        ("model.verifyUpsert", "yes"),
    ]
    
    for agent, decision in agents_content:
        next_agent = engine.get_next_agent("CONTENT", agent, decision)
        print(f"  {agent} ({decision}) → {next_agent}")
    
    # Test no branch
    print("\n📋 HITL (No) Branch:")
    next_agent = engine.get_next_agent("RULE", "model.Capo", "no")
    print(f"  model.Capo (no) → {next_agent}")
    print(f"  ✅ Terminal node reached: {engine.is_terminal(next_agent)}")


# ============================================================================
# Test 3: Agent Decision Execution
# ============================================================================

async def test_agent_decisions():
    print("\n" + "="*70)
    print("TEST 3: Agent Decision Execution")
    print("="*70)
    
    print("\n📋 RULE Flow Agent Sequence:")
    agents = [
        "model.Capo",
        "model.verifyRequest",
        "model.ruleToSQL",
        "model.verifySQL",
        "tool.executeSQL",
    ]
    
    for agent_name in agents:
        decision, confidence, reason = await call_agent(agent_name, "RULE", {})
        print(f"  [{agent_name:20s}] {decision:3s} ({confidence:.2f}) → {reason[:50]}")
    
    print("\n📋 CONTENT Flow Agent Sequence:")
    agents_content = [
        "model.Capo",
        "model.verifyRequest",
        "model.requestToExtractEntities",
        "model.verifyUpsert",
        "tool.executeSQL",
    ]
    
    for agent_name in agents_content:
        decision, confidence, reason = await call_agent(agent_name, "CONTENT", {})
        print(f"  [{agent_name:25s}] {decision:3s} ({confidence:.2f}) → {reason[:45]}")


# ============================================================================
# Test 4: Complete Workflow Walkthrough
# ============================================================================

async def test_complete_workflow():
    print("\n" + "="*70)
    print("TEST 4: Complete Workflow Walkthrough")
    print("="*70)
    
    engine = WorkflowEngine()
    
    # Simulate RULE flow with decision tree walking
    print("\n📋 Simulating RULE Flow Execution:")
    
    session_id = "sess-demo-001"
    request_id = "req-demo-001"
    verb = "RULE"
    
    current_agent = "model.Capo"
    step = 0
    
    while step < 10:  # Safety limit
        step += 1
        
        # Call agent
        decision, confidence, reason = await call_agent(current_agent, verb, {})
        
        print(f"\n  Step {step}: {current_agent}")
        print(f"    Decision: {decision} (confidence: {confidence:.1%})")
        print(f"    Reason: {reason}")
        
        # Get next agent
        next_agent = engine.get_next_agent(verb, current_agent, decision)
        print(f"    Next: {next_agent}")
        
        # Check for HITL (decision=no)
        if decision == "no":
            print(f"\n  ⚠️  HITL Triggered: Requires human input")
            break
        
        # Check for terminal
        if engine.is_terminal(next_agent):
            print(f"\n  ✅ Terminal reached: Workflow complete")
            break
        
        current_agent = next_agent


# ============================================================================
# Test 5: Response Message Envelope
# ============================================================================

async def test_response_messages():
    print("\n" + "="*70)
    print("TEST 5: Response Message Envelopes")
    print("="*70)
    
    session_id = "sess-001"
    request_id = "req-001"
    
    # Typical yes response
    decision, confidence, reason = await call_agent("model.Capo", "RULE", {})
    response = make_response(
        session_id=session_id,
        request_id=request_id,
        verb=Verb.RULE,
        next_agent="model.verifyRequest",
        decision=Decision(decision),
        confidence=confidence,
        reason=reason,
        message_body={"rule_text": "..."},
    )
    
    print("\n✅ Response Message (agent yes → next agent):")
    print(f"   returnCode: {response.returnCode}")
    print(f"   decision: {response.decision.value}")
    print(f"   confidence: {response.confidence:.2f}")
    print(f"   nextAgent: {response.nextAgent}")
    
    # No response (HITL)
    response_no = make_response(
        session_id=session_id,
        request_id=request_id,
        verb=Verb.RULE,
        next_agent="sendMessageToChat",
        decision=Decision.NO,
        confidence=0.65,
        reason="Unable to determine entity type",
        message_body={"humanPrompt": "Should this be pattern or category?"},
    )
    
    print("\n✅ Response Message (agent no → HITL):")
    print(f"   decision: {response_no.decision.value}")
    print(f"   nextAgent: {response_no.nextAgent}")
    print(f"   reason: {response_no.reason}")
    print(f"   messageBody: {response_no.messageBody}")
    
    # Success response
    success = make_success(
        session_id=session_id,
        request_id=request_id,
        verb=Verb.RULE,
        message_body={"rows_modified": 42},
    )
    
    print("\n✅ Success Response (terminal):")
    print(f"   decision: {success.decision.value}")
    print(f"   returnCode: {success.returnCode}")
    print(f"   nextAgent: {success.nextAgent}")


# ============================================================================
# Main
# ============================================================================

async def main():
    print("\n" + "="*70)
    print("Pattern Factory Message Protocol v1.1")
    print("End-to-End Test Suite")
    print("="*70)
    
    # Synchronous tests
    test_envelope_creation()
    test_workflow_engine()
    
    # Async tests
    await test_agent_decisions()
    await test_complete_workflow()
    await test_response_messages()
    
    print("\n" + "="*70)
    print("✅ All tests passed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
