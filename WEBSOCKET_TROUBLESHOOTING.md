# WebSocket Connection Troubleshooting

## Common Issue: "Not connected (status: disconnected)"

This error appears when the chat tries to send a message but the WebSocket is not connected.

## Quick Fixes

### 1. Ensure Backend is Running

Check if the API is responding:
```bash
curl http://localhost:8000/
```

**Expected output:**
```json
{
  "status": "ok",
  "message": "Pattern Factory API operational",
  "postgres": "postgresql://...",
  "timestamp": "..."
}
```

**If not working:**
```bash
cd /Users/dl/code/pattern-factory/backend
uvicorn services.api:app --reload --host 0.0.0.0 --port 8000
```

### 2. Check Frontend is Running

Verify frontend dev server:
```bash
curl http://localhost:5173/
```

**If not running:**
```bash
cd /Users/dl/code/pattern-factory
npm run dev
```

### 3. Verify WebSocket Endpoint

Test WebSocket accessibility:
```bash
curl -v http://localhost:8000/ws 2>&1 | grep -i "connection\|upgrade"
```

Should show HTTP upgrade headers or WebSocket response.

### 4. Hard Refresh Browser

The frontend may have cached old code:
```
Mac: Cmd + Shift + R
Windows: Ctrl + Shift + R
Or clear browser cache manually
```

### 5. Check Browser Console

Open DevTools (F12) → Console tab and look for:

```javascript
// Connected:
"WebSocket connected to Pitboss"
"Connected to Pattern Agent" (system message)

// Disconnected:
"WebSocket error: ..."
"WebSocket disconnected"

// Connection refused:
"WebSocket connection failed: ..."
```

## Detailed Debugging

### Step 1: Verify Backend is Running

```bash
# Check API is operational
curl -s http://localhost:8000/ | jq .

# Should output JSON with status: "ok"
```

### Step 2: Test DSL Loading

Backend should load the DSL when it starts. Look for:

```
context_builder.py - INFO - ✅ Loaded Pattern Factory DSL: ...
context_builder.py - INFO -    SYSTEM sections: ...
context_builder.py - INFO -    DATA tables: 18
```

If you don't see this in the backend logs:
```bash
# Test DSL loading
cd /Users/dl/code/pattern-factory
python backend/test_dsl_loading.py
```

### Step 3: Check Network in DevTools

1. Open DevTools (F12)
2. Go to **Network** tab
3. Filter by **WS** (WebSocket)
4. Click chat icon to open drawer
5. Look for WebSocket connection attempt

**What you should see:**
- WebSocket connection to `ws://localhost:8000/ws`
- Status: **101 Switching Protocols** (green)

**If you see:**
- Status: **404** → WebSocket endpoint not found
- Status: **500** → Backend error
- No WS request → Frontend not attempting connection

### Step 4: Browser Console Logs

Make sure console logging is enabled and check for:

```javascript
// Good signs:
"WebSocket connected to Pitboss"
"Connected to Pattern Agent"

// Bad signs:
"WebSocket connection failed"
"Failed to parse WebSocket message"
"Not connected (status: disconnected)"
```

## Common Causes

### Backend Not Running
- **Symptom**: "Not connected" when chat opens
- **Fix**: Start backend with `uvicorn services.api:app --reload`

### Frontend Cache Issue
- **Symptom**: Connection status never changes
- **Fix**: Hard refresh browser (Cmd+Shift+R on Mac)

### Wrong WebSocket URL
- **Symptom**: WebSocket fails to connect in Network tab
- **Check**: `WS_URL = 'ws://localhost:8000/ws'` in ChatInterface.svelte
- **Fix**: Update URL if backend runs on different port

### PostgreSQL Not Connected
- **Symptom**: Backend starts but WebSocket connection fails
- **Check**: Backend logs for "Postgres connected" message
- **Fix**: Ensure PostgreSQL is running and connection string is correct

### OpenAI API Key Missing
- **Symptom**: Backend runs but rules don't execute
- **Check**: `.env` file has `OPENAI_API_KEY=...`
- **Fix**: Add valid OpenAI API key to `.env` and restart backend

## Connection Flow

```
1. Browser loads chat interface
   ↓
2. onMount hook runs (when drawer opens)
   ↓
3. connectWebSocket() creates WebSocket
   ↓
4. ws://localhost:8000/ws connection attempt
   ↓
5a. SUCCESS → onopen() fires → "connected" status
   ↓
5b. FAILURE → onerror() fires → "error" status
   ↓
5c. TIMEOUT → onclose() fires → "disconnected" status
```

## Testing After Fix

### Test 1: Connection
1. Click chat icon
2. Wait 1-2 seconds
3. Check status shows **"connected"** (green dot)
4. Message says "Connected to Pattern Agent"

### Test 2: Send Rule
1. Type: `run Find all patterns`
2. Press Enter
3. Message appears (blue, right)
4. Typing indicator shows (● ● ●)
5. Response appears (gray, left)

### Test 3: Reconnection
1. Restart backend (Ctrl+C then uvicorn)
2. Chat shows "disconnected"
3. Messages still visible
4. After backend restarts, try another rule
5. Should reconnect automatically

## Port Conflicts

If port 8000 is already in use:

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
uvicorn services.api:app --port 8001 --reload
```

Then update `WS_URL` in ChatInterface.svelte:
```typescript
const WS_URL = 'ws://localhost:8001/ws';
```

## Recent Fix

**Fixed**: Duplicate `onMount` hooks in ChatInterface.svelte that were preventing WebSocket connection initialization.

**What was wrong:**
- Two `onMount` hooks in same component
- Second hook overrode the first
- `connectWebSocket()` never called

**What was fixed:**
- Consolidated `onMount` hooks
- Combined functionality (connect + scroll)
- Now connection initializes properly

## Still Having Issues?

Check this checklist:

- [ ] Backend running: `curl http://localhost:8000/`
- [ ] Frontend running: Page loads at http://localhost:5173
- [ ] WebSocket endpoint accessible: Check Network tab in DevTools
- [ ] Browser console shows no errors
- [ ] DSL loads: Check backend logs for "✅ Loaded Pattern Factory DSL"
- [ ] PostgreSQL connected: Check backend logs
- [ ] OpenAI key set: Check `.env` file
- [ ] No port conflicts: `lsof -i :8000`
- [ ] Browser cache cleared: Hard refresh (Cmd+Shift+R)

If all pass, try:
1. Close chat drawer
2. Restart frontend: `npm run dev`
3. Reopen chat
4. Check console for errors

---

**Last Updated**: November 24, 2025  
**Fixed Issue**: Duplicate onMount hooks preventing WebSocket connection
