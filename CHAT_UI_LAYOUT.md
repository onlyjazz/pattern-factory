# Chat UI Layout - Visual Guide

## Header Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ [Logo] Pattern Factory    [Chat Icon] [Search Box]              │
│                                          ↓ click                 │
└─────────────────────────────────────────────────────────────────┘
```

## Open Chat Drawer (Desktop)

```
┌──────────────────────────────────────────┬──────────────┐
│                                          │ Pattern      │
│                                          │ Agent      X │
│  Main Content                            ├──────────────┤
│  (dimmed behind overlay)                 │              │
│                                          │ Messages     │
│                                          │              │
│                                          ├──────────────┤
│                                          │ [Input Area] │
│                                          │ [Send]       │
└──────────────────────────────────────────┴──────────────┘
  ↑ Semi-transparent overlay (click to close)
```

## Open Chat Drawer (Mobile)

```
┌──────────────────────────────────┐
│ Pattern Agent                  X │
├──────────────────────────────────┤
│                                  │
│ Messages                         │
│                                  │
├──────────────────────────────────┤
│ [Input Area - Full Width]        │
│ [Send]                           │
└──────────────────────────────────┘
```

## Closed State

All screen space used by main content:

```
┌─────────────────────────────────────────────────────────────────┐
│ [Logo] Pattern Factory    [Chat Icon] [Search Box]              │
└─────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ Sidebar    │    Main Content                                   │
│            │                                                   │
│ • Patterns │    • Full Page                                    │
│ • Views    │    • No Chat Drawer                               │
│            │                                                   │
└────────────────────────────────────────────────────────────────┘
```

## Message Display

### User Message (Right-aligned, Blue)
```
┌────────────────────────────────────┐
│      [User Message Text Here]  12:34│
└────────────────────────────────────┘
```

### Agent Message (Left-aligned, Gray)
```
┌────────────────────────────────────┐
│ [Agent Response Here]           12:35│
└────────────────────────────────────┘
```

### Typing Indicator
```
┌────────────────────────────────────┐
│ [● ● ●]                             │
└────────────────────────────────────┘
```

## Input Area

```
┌────────────────────────────────────────────────────┐
│ [Expanding Textarea - Auto-grows up to 200px]  ⬆ │
│ Ask me anything about patterns...            [●] │
└────────────────────────────────────────────────────┘
   ↑ Rounded pill design, Material Icons
   Rounded corners, light blue on send
```

## Interaction Flows

### Opening Chat
```
1. Click [Chat Icon] in header
   ↓
2. Backdrop fades in (300ms animation)
   ↓
3. Drawer slides in from right (300ms animation)
   ↓
4. Chat ready for input
```

### Closing Chat
```
1. User action:
   - Click [X] button, OR
   - Press ESC key, OR
   - Click backdrop
   ↓
2. Drawer slides out (300ms animation)
   ↓
3. Backdrop fades out (300ms animation)
   ↓
4. Back to main content (full screen)
   ↓
5. Messages preserved for next open
```

### Sending Message
```
1. Type in textarea
   ↓
2. Press Enter (or Shift+Enter for newline)
   ↓
3. Message appears (blue, right-aligned)
   ↓
4. Typing indicator shows (● ● ●)
   ↓
5. 500ms delay (Stage 1 echo)
   ↓
6. Echo message appears (gray, left-aligned)
   ↓
7. Ready for next message
```

## Responsive Behavior

### Desktop (>768px)
- Drawer: 500px wide
- Sidebar: Visible (12rem)
- Main content: Visible with overlay

### Mobile (<768px)
- Drawer: Full width (100%)
- Sidebar: Hidden by drawer
- Main content: Fully covered by overlay

## Animations

### Drawer Slide
```
Closed:  ████████████████████| 
         (off-screen right)

Opening: ███████████████████░░░░
         ███████████░░░░░░░░░░░░
         ███░░░░░░░░░░░░░░░░░░░░

Open:    ░░░░░░░░░░░░░░░░░░████████
         (in view)
```

### Backdrop Fade
```
Closed:  ░░░░░░░░░░░░░░░░░░░░░░░░░░ (opacity: 0)
Opening: ░░░░░░░░░░░░░░░░░░░░░░░░░░
         ██████░░░░░░░░░░░░░░░░░░░░ (fading in)
Open:    ████████████████████████████ (opacity: 1)
```

All animations use 300ms ease timing function.

## Color Scheme

| Element | Color | Use |
|---------|-------|-----|
| Header | #039be5 | Blue background |
| Chat Button | White | Icon color |
| Chat Button Hover | rgba(255,255,255,0.1) | Light background |
| User Messages | #039be5 | Blue bubble |
| Agent Messages | #f5f5f5 | Light gray bubble |
| Backdrop | rgba(0,0,0,0.5) | Semi-transparent overlay |
| Send Button | #039be5 | Blue button |
| Send Disabled | #ccc | Gray when disabled |

## Accessibility

- Chat icon has title and aria-label
- Close button has title and aria-label
- Escape key closes drawer
- Proper z-index management (1000)
- Semantic HTML elements
- Keyboard focus management
