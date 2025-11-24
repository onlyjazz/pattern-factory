# Pattern Agent Chat Interface

## Overview

This document describes the frontend implementation of the Pattern Agent chat interface, which provides real-time communication with AI agents via the Pitboss supervisor system.

## Stage 1: Message Exchange UI (Current)

### Components

The chat interface is built from three main Svelte components:

#### 1. **ChatMessage.svelte** (`src/lib/ChatMessage.svelte`)
Displays individual messages in the conversation.

**Props:**
- `role: 'user' | 'agent'` - Message sender (default: 'user')
- `content: string` - Message text (default: '')
- `timestamp: Date | null` - Optional timestamp (default: null)

**Features:**
- Different styling for user (blue) vs agent (gray) messages
- Smooth slide-in animation
- Optional timestamp display
- Responsive max-width (70% of container)
- Proper text wrapping and word breaking

#### 2. **ChatInput.svelte** (`src/lib/ChatInput.svelte`)
Textarea input with send button styled like ChatGPT.

**Props:**
- `isLoading: boolean` - Disable input while waiting for response (default: false)
- `onSend: (message: string) => void` - Callback when message is sent

**Features:**
- Auto-expanding textarea (up to 200px max height)
- Up arrow button (Material Icons: `arrow_upward`)
- Loading spinner while waiting for response
- Keyboard shortcuts:
  - `Enter` to send message
  - `Shift + Enter` for newline
  - `Cmd/Ctrl + Enter` to send
- Rounded pill-shaped design matching modern chat UIs
- Disabled state when loading or input is empty

#### 3. **ChatInterface.svelte** (`src/lib/ChatInterface.svelte`)
Main orchestrator component managing message flow.

**Features:**
- Message history management with unique IDs
- Auto-scroll to latest message
- Empty state with helpful prompt
- "Typing..." indicator with animated dots
- Clear conversation button
- **Stage 1 Echo Behavior**: When user sends a message, the agent responds after a 500ms delay by echoing the same message back

### Drawer Component

**ChatDrawer.svelte** (`src/lib/ChatDrawer.svelte`)
- Modal drawer component that slides in from the right
- Renders full-height chat interface
- Dismissible via:
  - Close button in chat header
  - Backdrop click
  - Escape key press
- Smooth slide-in/out animation
- Semi-transparent backdrop overlay
- Responsive: full width on mobile, max 500px on desktop

## UI/UX Features

### Design System Integration
- Uses existing Material Icons from `main.css`
- Follows project color scheme:
  - User messages: `#039be5` (light blue)
  - Agent messages: `#f5f5f5` (light gray)
  - Primary interactive color: `#039be5`
- Consistent typography and spacing with application

### Message Styling
- **User messages**: Blue bubbles on the right, `border-bottom-right-radius: 4px`
- **Agent messages**: Gray bubbles on the left, `border-bottom-left-radius: 4px`
- Custom scrollbar styling for better UX
- Smooth animations for message appearance

### Responsive Layout
- Full viewport height utilization
- Flexible message containers
- Touch-friendly button sizes (44px minimum)
- Maintains readability on various screen sizes

## UI Integration

### Header Chat Button
- Chat icon in the application header (top-right)
- Click to open/close the chat drawer
- Visible from any page in the application
- Smooth slide-in/out animation

## Current Stage 1 Functionality

### Message Flow
1. User clicks chat icon in header
2. Chat drawer slides in from the right
3. User enters text in textarea
4. User clicks send button or presses Enter
5. User message appears in chat
6. Interface shows "typing..." indicator
7. After 500ms delay, agent echoes the message back
8. Message appears as agent response
9. User can close drawer by:
   - Clicking the X button in the chat header
   - Clicking the semi-transparent backdrop
   - Pressing Escape key

### Usage Example

The chat is automatically available from any page via the header chat icon. It can also be embedded directly:

```svelte
<script>
  import ChatDrawer from '$lib/ChatDrawer.svelte';
  
  let chatOpen = $state(false);
</script>

<ChatDrawer isOpen={chatOpen} onClose={() => chatOpen = false} />

<button on:click={() => chatOpen = true}>Open Chat</button>
```

## Stage 2: WebSocket Integration (Current)

### Implementation
- ✅ Connected to backend Pitboss `/ws` endpoint
- ✅ Replaced echo behavior with actual AI agent responses
- ✅ Connection state management (connecting, connected, disconnected, error)
- ✅ Visual connection status indicator with pulsing green dot
- ✅ Error handling with user-friendly messages

### Features
- Users type `run ` followed by natural language rule
- Frontend sends `{"type": "run_rule", "rule_code": "..."}` to WebSocket
- Pitboss processes rule via `process_rule_request()`
- LLM (GPT-4o) generates SQL from natural language
- SQL executed and results displayed in chat
- Connection status always visible in header

### Message Format
Users write: `run Find all patterns with description containing test`

## Future Stages

### Stage 3: Enhanced Features
- Add message persistence to localStorage
- Implement conversation history/sessions
- Add syntax highlighting for code responses
- Add rule suggestions/autocomplete
- Add result export to CSV
- Implement message reactions/feedback

### Stage 3: Advanced Features
- Message persistence (local storage or database)
- Conversation history/sessions
- Code syntax highlighting for agent responses
- File upload support
- Message editing/deletion
- Conversation search

## Development

### Running the Chat Interface

1. Start the dev server:
   ```bash
   npm run dev
   ```

2. Navigate to `http://localhost:5173`

3. Click the chat icon in the header (top-right) to open the drawer

4. Type a message and press Enter or click the send button

5. Close with the X button, Escape key, or click the backdrop

### TypeScript Types

The `Message` interface used internally:
```typescript
interface Message {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: Date;
}
```

### Styling Customization

All styling is scoped within component `<style>` blocks. Key classes:
- `.chat-interface` - Main container
- `.chat-header` - Header with title and clear button
- `.messages-container` - Scrollable message area
- `.chat-input-container` - Input section
- `.chat-message` - Individual message wrapper
- `.message-bubble` - Message content styling

## Technical Notes

- Uses Svelte 5 reactive declarations
- No external chat UI library - custom implementation
- Fully typed with TypeScript
- Accessible markup with ARIA labels
- Event handling for Enter key with proper modifiers
- Auto-scroll uses `scrollTop` assignment with `setTimeout` for DOM update sync

## Integration with Pitboss

Once WebSocket integration is added in Stage 2, the flow will be:

1. User sends message via `ChatInput`
2. `ChatInterface` formats message as WebSocket frame: `{"type": "run_rule", "rule_code": "..."}`
3. Backend Pitboss supervisor processes via LLM
4. Agent response received over WebSocket
5. `ChatInterface` adds agent message to conversation
6. Message renders via `ChatMessage` component
