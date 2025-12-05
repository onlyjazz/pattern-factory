# Pattern Factory - Stage 2 Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Browser (Client)                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    SvelteKit Frontend                     │  │
│  │                                                           │  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐   │  │
│  │  │ Header   │  │ Sidebar  │  │   Chat Drawer          │   │  │
│  │  │ [💬]     │  │          │  │  ┌────────────────────┐│   │  │
│  │  │  Button  │  │ Patterns │  │  │ ChatInterface      ││ │ │
│  │  │          │  │ Views    │  │  │                    ││ │ │
│  │  └──────────┘  └──────────┘  │  │ Status: connected  ││ │ │
│  │       ▲                      │  │ Messages: [...]    ││ │ │
│  │       │                      │  │ Input: run [rule]  ││ │ │
│  │       │                      │  └────────────────────┘│ │ │
│  │       └───────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│                           │                                      │
│                           │ onClick                              │
│                           ▼                                      │
│                    ┌──────────────┐                              │
│                    │  onClose     │                              │
│                    │  onChatClick │                              │
│                    └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ WebSocket
                           │ wss://localhost:8000/ws
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend (Server)                         │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              FastAPI Service (services/api.py)            │ │
│  │                                                            │ │
│  │  @app.websocket("/ws")                                    │ │
│  │  async def websocket_endpoint(ws: WebSocket):             │ │
│  │    ├─ Accept connection                                   │ │
│  │    ├─ Create Pitboss instance                             │ │
│  │    └─ Receive messages loop                               │ │
│  │       ├─ type: "run_rule"                                 │ │
│  │       │   → process_rule_request()                        │ │
│  │       ├─ type: "run_workflow"                             │ │
│  │       │   → run_workflow()                                │ │
│  │       └─ Send response back                               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                           │                                      │
│                           ▼                                      │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │          Pitboss Supervisor (pitboss/supervisor.py)       │ │
│  │                                                            │ │
│  │  process_rule_request(rule_code, rule_id)                 │ │
│  │    ├─ Build context from pattern-factory.yaml             │ │
│  │    ├─ Call ContextBuilder                                 │ │
│  │    └─ Call _process_single_rule()                         │ │
│  │       ├─ 1. Build LLM context (SYSTEM + DATA)             │ │
│  │       ├─ 2. Call sql_pitboss tool (GPT-4o)                │ │
│  │       ├─ 3. Call data_table tool (Create view)            │ │
│  │       ├─ 4. Call register_rule tool (Save metadata)       │ │
│  │       ├─ 5. Call register_view tool (Record view)         │ │
│  │       └─ 6. Send result to frontend                       │ │
│  └───────────────────────────────────────────────────────────┘ │
│                           │                                      │
│         ┌─────────────────┼─────────────────┐                    │
│         ▼                 ▼                 ▼                    │
│  ┌────────────┐  ┌──────────────┐  ┌────────────┐              │
│  │  OpenAI    │  │ PostgreSQL   │  │ Tool       │              │
│  │  GPT-4o    │  │  Database    │  │ Registry   │              │
│  │            │  │              │  │            │              │
│  │ - Generates│  │ - Patterns   │  │ - sql_     │              │
│  │   SQL from │  │ - Rules      │  │   pitboss  │              │
│  │   natural  │  │ - Views      │  │ - data_    │              │
│  │   language │  │ - System log │  │   table    │              │
│  │            │  │              │  │ - register │              │
│  └────────────┘  └──────────────┘  │   _rule    │              │
│                                     │ - register │              │
│                                     │   _view    │              │
│                                     └────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

## Message Flow Sequence

```
User (Browser)          Frontend             Backend             Database
    │                      │                   │                    │
    │── Click Chat ────────>│                   │                    │
    │                      │                   │                    │
    │                      │── Connect WS ────>│                    │
    │                      │<─ ACK ────────────│                    │
    │                      │                   │                    │
    │<── Show "connected" ─│                   │                    │
    │                      │                   │                    │
    │── Type & Send ───────>│                   │                    │
    │  "run Find patterns"  │                   │                    │
    │                      │                   │                    │
    │                      │── Parse "run" ────│                    │
    │                      │  Extract rule     │                    │
    │                      │                   │                    │
    │                      │── WS Send ───────>│                    │
    │                      │  {"type": "run_   │                    │
    │                      │   rule", "rule_   │                    │
    │                      │   code": "Find    │                    │
    │                      │   patterns"}      │                    │
    │                      │                   │                    │
    │<── Show Typing ──────│<─ Processing ─────│                    │
    │   (● ● ●)           │   Pitboss         │                    │
    │                      │                   │                    │
    │                      │                   │── Build Context ──>│
    │                      │                   │   pattern-factory. │
    │                      │                   │   yaml             │
    │                      │                   │<─ Schema Info ─────│
    │                      │                   │                    │
    │                      │                   │── Call OpenAI ────>│
    │                      │                   │   GPT-4o           │
    │                      │                   │   (2-5 sec)        │
    │                      │                   │<─ SQL Query ───────│
    │                      │                   │                    │
    │                      │                   │── Execute SQL ────>│
    │                      │                   │   CREATE TABLE     │
    │                      │                   │<─ Results ─────────│
    │                      │                   │   5 rows           │
    │                      │                   │                    │
    │                      │                   │── Register View ──>│
    │                      │                   │   Save metadata    │
    │                      │                   │<─ ACK ─────────────│
    │                      │                   │                    │
    │                      │<─ WS Response ────│                    │
    │                      │  {"type": "rule_  │                    │
    │                      │   result",        │                    │
    │                      │   "message": "Rule│                    │
    │                      │   find_patterns → │                    │
    │                      │   5 rows → ..."}  │                    │
    │                      │                   │                    │
    │<─ Agent Message ─────│                   │                    │
    │  (gray, left)        │                   │                    │
    │  "Rule find_         │                   │                    │
    │   patterns → 5 rows" │                   │                    │
    │                      │                   │                    │
    │── Type New Rule ─────>│                   │                    │
    │                      │── Another WS ────>│                    │
    │                      │   Send...         │                    │
```

## Data Structures

### Frontend → Backend (WebSocket)
```
{
  "type": "run_rule",
  "rule_code": "Find all patterns where kind equals pattern",
  "rule_id": "rule_1732430862456"
}
```

### Backend → Frontend (WebSocket - Success)
```
{
  "type": "rule_result",
  "message": "Rule find_all_patterns_where... → 42 rows → rule_find_all_patterns_where_kind_equals_pattern_1732430862456",
  "timestamp": "2025-11-24T12:30:45.123Z"
}
```

### Backend → Frontend (WebSocket - Error)
```
{
  "type": "error",
  "rule": "find_patterns_invalid",
  "message": "Invalid SQL generated: column 'unknown_field' does not exist",
  "timestamp": "2025-11-24T12:30:45.123Z"
}
```

## Component Hierarchy

```
Application Layout
├── Header
│   ├── Logo
│   ├── Title
│   ├── [💬] Chat Button ◄─── User clicks here
│   └── Search Box
├── Sidebar
│   ├── Patterns Link
│   └── Views List
├── Main Content
│   └── Current Page
└── ChatDrawer (modal overlay)
    ├── Semi-transparent Backdrop (click to close)
    └── ChatInterface ◄─── WebSocket happens here
        ├── Chat Header
        │   ├── "Pattern Agent"
        │   ├── Connection Status (connected/error/disconnected)
        │   ├── [🗑] Clear Button
        │   └── [✕] Close Button
        ├── Messages Container
        │   ├── ChatMessage (user - blue, right)
        │   ├── ChatMessage (agent - gray, left)
        │   ├── ChatMessage (system - gray, left)
        │   └── Typing Indicator (● ● ●)
        └── ChatInput
            ├── Auto-expanding Textarea
            └── [⬆] Send Button
```

## State Management

### ChatInterface Local State
```
messages: Message[]
  - id: string
  - role: 'user' | 'agent'
  - content: string
  - timestamp: Date

isLoading: boolean
connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
websocket: WebSocket | null
```

### Layout Global State
```
chatDrawerOpen: boolean
  - true: Drawer is visible
  - false: Drawer is hidden
```

## Error Handling Flow

```
Frontend Sends Rule
    ↓
Connection Check
├─ Not connected?
│  └─ Show: "❌ Not connected (status: disconnected)"
│
├─ Connected ✓
│  └─ Send to WebSocket
│     ↓
│     Backend Processes
│     ├─ Success
│     │  └─ Send: {"type": "rule_result", "message": "..."}
│     │     ↓
│     │     Frontend Shows: "Rule ... → X rows → table_name"
│     │
│     └─ Error
│        └─ Send: {"type": "error", "message": "..."}
│           ↓
│           Frontend Shows: "❌ Error: [message]"
│
└─ Network Error
   └─ Show: "❌ Failed to send request: [error]"
      Log to console
```

## Timeline (Performance)

```
User Action                                    Time
├─ Click Send                                  0ms
├─ Parse message                               ~1ms
├─ Create WebSocket message                    ~1ms
├─ Send to backend                             ~10ms (network)
├─ Backend receives                            +10ms (network)
├─ Build Pitboss context                       ~50ms
├─ Prepare LLM message                         ~10ms
├─ Call OpenAI GPT-4o                          ~2000-5000ms ⏳
├─ Parse SQL response                          ~10ms
├─ Execute SQL                                 ~100-500ms
├─ Create materialized view                    ~100-200ms
├─ Register rule & view                        ~50ms
├─ Send result to frontend                     ~10ms (network)
├─ Frontend receives                           +10ms (network)
├─ Parse message & display                     ~5ms
└─ User sees response                          ~3-6 seconds total
```

## Security Considerations

- ✅ WebSocket accepts connections from any origin (CORS enabled)
- ✅ Input validation: "run " prefix required
- ✅ Backend validates rule code before LLM
- ✅ SQL queries generated by LLM and executed in transaction
- ⚠️ No authentication/authorization (in-development setup)
- ⚠️ Error messages expose some system details (useful for debugging)

## Future Enhancements (Stage 3+)

```
┌─ Message Persistence
│  └─ localStorage / IndexedDB
│
├─ Auto-reconnection
│  └─ Exponential backoff
│
├─ Message Feedback
│  └─ Reactions / Rating
│
├─ Results Export
│  └─ CSV / JSON download
│
├─ Advanced Filtering
│  └─ Result filtering UI
│
└─ Conversation History
   └─ Session management
```

---

**Last Updated**: November 24, 2025
**Stage**: 2 - WebSocket Integration ✅
**Next**: Stage 3 - Enhanced Features
