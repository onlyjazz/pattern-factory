# Stage 2: WebSocket Integration - Testing Guide

## Overview

Stage 2 connects the frontend chat interface to the Pitboss supervisor via WebSocket. Users can now write natural language rules in the chat and send them to the backend for processing.

## How It Works

### Message Format

Users type messages starting with `run` followed by their rule:

```
run Find all patterns with description containing "test"
```

### Processing Flow

1. **User Types Message** in chat
2. **Frontend Parses** the message:
   - Extracts text after "run "
   - Creates WebSocket request: `{"type": "run_rule", "rule_code": "...", "rule_id": "..."}`
3. **Sends via WebSocket** to `ws://localhost:8000/ws`
4. **Pitboss Supervisor Receives** the request at `process_rule_request()`
5. **Pitboss Processes**:
   - Builds LLM context from `pattern-factory.yaml`
   - Calls OpenAI GPT-4o to translate rule to SQL
   - Executes SQL and creates materialized view
   - Registers rule in database
   - Sends results back via WebSocket
6. **Frontend Receives** response and displays agent message

## Testing Setup

### Prerequisites

1. **Backend Running**:
   ```bash
   cd backend
   uvicorn services.api:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend Running**:
   ```bash
   npm run dev
   ```

3. **PostgreSQL** connected and schema initialized
4. **OPENAI_API_KEY** set in `.env`

### Step-by-Step Testing

#### Test 1: Connection Status

1. Open http://localhost:5173
2. Click the chat icon in the header
3. **Expected**: 
   - Green "connected" indicator appears in chat header
   - Pulsing green dot next to status text
   - Message: "Connected to Pattern Agent"

#### Test 2: Invalid Message (No "run" prefix)

1. Type: `Hello`
2. Press Enter
3. **Expected**:
   - User message appears (blue, right)
   - Agent response: Info message about starting with "run"

#### Test 3: Simple Rule Query

1. Type: `run Find all patterns`
2. Press Enter
3. **Expected**:
   - User message appears (blue, right)
   - Typing indicator appears (● ● ●)
   - Agent message appears with result from Pitboss
   - Example response: `Rule find_all_patterns → 5 rows → rule_find_all_patterns_...`

#### Test 4: Complex Rule

1. Type: `run Find all patterns where kind equals pattern and description contains test`
2. Press Enter
3. **Expected**:
   - Processing occurs
   - Result message with table name and row count

#### Test 5: WebSocket Reconnection

1. Disconnect backend (kill `uvicorn` process)
2. Try sending a message: `run Find all patterns`
3. **Expected**:
   - Error message: "❌ Not connected (status: disconnected)"
4. Restart backend
5. **Expected**:
   - Connection status changes to "connected"
   - Green pulsing dot returns

#### Test 6: Error Handling

1. Send invalid rule: `run !!@#$%^&*()`
2. **Expected**:
   - Error message from Pitboss explaining the issue
   - Error prefixed with ❌

#### Test 7: Chat Persistence

1. Send: `run Find all patterns`
2. Close drawer (X button or Escape)
3. Reopen chat (click header icon)
4. **Expected**:
   - All previous messages still visible
   - Messages persist until "Clear" button is clicked

#### Test 8: Clear Chat

1. Send several messages
2. Click the trash icon (Clear button) in header
3. **Expected**:
   - All messages cleared
   - Connection status still shows "connected"
   - Ready for new conversation

## Message Examples

### Basic Query
```
run Find all patterns
```

### Filtered Query
```
run Find patterns where kind equals pattern
```

### Text Search
```
run Find patterns with description containing workflow
```

### Complex Query
```
run Find all patterns created in the last 30 days where the kind is not anti-pattern
```

## Response Format

### Success Response (from Pitboss)
```json
{
  "type": "rule_result",
  "message": "Rule find_all_patterns → 5 rows → rule_find_all_patterns_1732430862456",
  "timestamp": "2025-11-24T12:30:00.000Z"
}
```

### Error Response
```json
{
  "type": "error",
  "rule": "invalid_rule_name",
  "message": "Invalid SQL generated: ...",
  "timestamp": "2025-11-24T12:30:00.000Z"
}
```

## Frontend Connection States

### Connected (Green)
- WebSocket is open
- Ready to send rules
- Status shows "connected" with pulsing dot

### Connecting (Gray)
- WebSocket is establishing connection
- Status shows "connecting"
- Send buttons disabled

### Disconnected (Gray)
- WebSocket not connected
- Status shows "disconnected"
- Error message shown when trying to send

### Error (Red)
- Connection failed or errored
- Status shows "error" in red
- Check browser console for details

## Debugging

### Browser Console

Open DevTools (F12) and check Console tab:

1. **Connection logs**:
   ```
   WebSocket connected to Pitboss
   ```

2. **Send logs**:
   ```
   Sending to Pitboss: {type: "run_rule", rule_code: "...", rule_id: "..."}
   ```

3. **Receive logs**:
   ```
   Received from Pitboss: {type: "rule_result", message: "..."}
   ```

4. **Errors**:
   ```
   WebSocket error: ...
   Failed to parse WebSocket message: ...
   ```

### Backend Logs

Check the `uvicorn` terminal:

1. **Connection**:
   ```
   🔌 WebSocket connected
   🧠 Pitboss instance created for WebSocket
   ```

2. **Rule Processing**:
   ```
   [Supervisor] Received rule request: Find all patterns
   ```

3. **Errors**:
   ```
   [Supervisor] Crash in rule find_all_patterns: ...
   ```

### Common Issues

#### Issue: "Not connected" message

**Cause**: Backend not running or WebSocket URL incorrect

**Fix**:
- Ensure `uvicorn` is running on port 8000
- Check `.env` file has correct OPENAI_API_KEY
- Verify frontend is trying to connect to `ws://localhost:8000/ws`

#### Issue: Message sending but no response

**Cause**: Backend processing taking too long or SQL generation failed

**Fix**:
- Check backend logs for errors
- Verify OpenAI API key is valid
- Check database connection is working
- Try simpler rule first

#### Issue: WebSocket connects then immediately disconnects

**Cause**: Backend crash or connection timeout

**Fix**:
- Check backend logs for crashes
- Verify Postgres is running
- Check system resources (memory, CPU)
- Restart backend

#### Issue: CORS errors in browser console

**Cause**: Frontend and backend on different origins (shouldn't happen)

**Fix**:
- Ensure backend CORS middleware is enabled
- Check API returns CORS headers

## Performance Notes

### Expected Timings

- **Connection**: < 500ms
- **Rule parsing**: < 100ms
- **SQL generation (LLM)**: 2-5 seconds
- **SQL execution**: < 500ms (depends on query complexity)
- **Total**: 3-6 seconds per rule

### Optimization Tips

1. Keep rules specific (helps LLM generate better SQL)
2. Avoid overly complex conditions
3. Use simple field names in rules
4. Check `pattern-factory.yaml` is up-to-date with schema

## Next Steps (Stage 3)

- [ ] Add message persistence to localStorage
- [ ] Implement conversation history
- [ ] Add syntax highlighting for code responses
- [ ] Add rule suggestions/autocomplete
- [ ] Add result export to CSV
- [ ] Implement message reactions/feedback
