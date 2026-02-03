"""
Pattern Factory Message Protocol v1.1
Unified envelope for all front-end <-> backend communication.

All messages (request, response, error) share this structure:
- type: request | response | error
- version: protocol version (1.1)
- timestamp: milliseconds since epoch
- session_id: conversation session ID
- request_id: unique request ID (req-001, req-002, ...)
- verb: RULE | CONTENT | GENERATE
- nextAgent: name of agent Pitboss will call next (e.g., model.Capo)
- returnCode: 0=continue, 1=success, negative=error
- decision: yes | no (for branching)
- confidence: 0.0-1.0 (agent self-reported confidence)
- reason: explanation for yes/no decision
- messageBody: verb-specific payload
"""

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, Optional, Literal
from enum import Enum
import time
import json


class MessageType(str, Enum):
    """Type of message."""
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"


class Verb(str, Enum):
    """Message verb (what the message is about)."""
    RULE = "RULE"
    CONTENT = "CONTENT"
    CARD = "CARD"
    GENERATE = "GENERATE"  # Generate risk model from card URL
    GENERIC = "GENERIC"  # Placeholder: LanguageCapo will determine actual verb


class Decision(str, Enum):
    """Agent decision for branching."""
    YES = "yes"
    NO = "no"


@dataclass
class MessageEnvelope:
    """Unified message envelope for Pattern Factory protocol."""
    
    # Protocol metadata
    type: MessageType
    version: str = "1.1"
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    
    # Tracing
    session_id: str = ""
    request_id: str = ""
    
    # Message semantics
    verb: Verb = Verb.RULE
    nextAgent: Optional[str] = None
    
    # Response metadata
    returnCode: int = 0  # 0=continue, 1=success, negative=error
    decision: Optional[Decision] = None  # yes|no
    confidence: float = 0.0  # 0.0-1.0
    reason: str = ""
    
    # Payload
    messageBody: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        data = asdict(self)
        # Convert enums to strings
        data["type"] = self.type.value
        data["verb"] = self.verb.value
        if self.decision:
            data["decision"] = self.decision.value
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageEnvelope":
        """Create envelope from dict (reverse of to_dict)."""
        # Convert string values back to enums with validation
        if isinstance(data.get("type"), str):
            try:
                data["type"] = MessageType(data["type"])
            except ValueError:
                raise ValueError(f"Invalid message type: '{data['type']}'")
        
        if isinstance(data.get("verb"), str):
            verb_str = data["verb"].strip() if data["verb"] else ""
            if not verb_str:
                raise ValueError("Verb field is empty or missing")
            try:
                data["verb"] = Verb(verb_str)
            except ValueError:
                available_verbs = ", ".join([v.value for v in Verb])
                raise ValueError(f"Invalid verb: '{verb_str}'. Available: {available_verbs}")
        
        if isinstance(data.get("decision"), str):
            try:
                data["decision"] = Decision(data["decision"])
            except ValueError:
                raise ValueError(f"Invalid decision: '{data['decision']}'")
        
        # Handle optional fields
        if "decision" not in data or data["decision"] is None:
            data["decision"] = None
        
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "MessageEnvelope":
        """Create envelope from JSON string."""
        return cls.from_dict(json.loads(json_str))


# ============================================================================
# Helper Functions
# ============================================================================

def make_request(
    session_id: str,
    request_id: str,
    verb: Verb,
    message_body: Dict[str, Any],
) -> MessageEnvelope:
    """Create a request message."""
    return MessageEnvelope(
        type=MessageType.REQUEST,
        session_id=session_id,
        request_id=request_id,
        verb=verb,
        nextAgent="model.Capo",  # Entry point
        messageBody=message_body,
    )


def make_response(
    session_id: str,
    request_id: str,
    verb: Verb,
    next_agent: Optional[str],
    decision: Decision,
    confidence: float,
    reason: str,
    message_body: Dict[str, Any],
    return_code: int = 0,
) -> MessageEnvelope:
    """Create a response message."""
    return MessageEnvelope(
        type=MessageType.RESPONSE,
        session_id=session_id,
        request_id=request_id,
        verb=verb,
        nextAgent=next_agent,
        decision=decision,
        confidence=confidence,
        reason=reason,
        messageBody=message_body,
        returnCode=return_code,
    )


def make_error(
    session_id: str,
    request_id: str,
    verb: Verb,
    error_message: str,
) -> MessageEnvelope:
    """Create an error message."""
    return MessageEnvelope(
        type=MessageType.ERROR,
        session_id=session_id,
        request_id=request_id,
        verb=verb,
        reason=error_message,
        returnCode=-1,
    )


def make_success(
    session_id: str,
    request_id: str,
    verb: Verb,
    message_body: Dict[str, Any],
) -> MessageEnvelope:
    """Create a success response."""
    return MessageEnvelope(
        type=MessageType.RESPONSE,
        session_id=session_id,
        request_id=request_id,
        verb=verb,
        nextAgent=None,
        decision=Decision.YES,
        confidence=1.0,
        reason="Success",
        messageBody=message_body,
        returnCode=1,
    )
