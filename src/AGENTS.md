# Consistent UI Refactoring - Implementation Guide

## CRITICAL: Accessibility Rules (Zero Tolerance)

**The Svelte a11y plugin will emit warnings that clutter the build log and make debugging impossible. Follow these rules EXACTLY to prevent ANY a11y warnings.**

### Rule 1: Never use `<div onclick>` or `<span onclick>`

❌ **NEVER**:
```svelte
<div onclick={handleClick}>Click me</div>
<span onclick={selectItem(item)}>Item name</span>
```

✅ **ALWAYS use `<button type="button">`**:
```svelte
<button type="button" onclick={handleClick}>Click me</button>
<button type="button" onclick={() => selectItem(item)}>Item name</button>
```

### Rule 2: All clickable buttons MUST support keyboard (Enter key)

❌ **WRONG** — no keyboard support:
```svelte
<button type="button" onclick={handleSubmit}>Submit</button>
```

✅ **CORRECT** — Enter key supported:
```svelte
<button
  type="button"
  onclick={handleSubmit}
  onkeydown={(e) => e.key === 'Enter' && handleSubmit()}
>
  Submit
</button>
```

### Rule 3: Modal dialogs MUST have proper accessibility structure

❌ **WRONG** — missing role, aria-labelledby, tabindex, or onclick on modal-content:
```svelte
{#if showModal}
  <div onclick={closeModal}>
    <div class="modal-content" onclick={(e) => e.stopPropagation()}>
      <h2>Modal Title</h2>
      <p>Content</p>
    </div>
  </div>
{/if}
```

✅ **CORRECT** — full a11y structure:
```svelte
{#if showModal}
  <div
    class="modal-overlay"
    role="presentation"
    onclick={closeModal}
    onkeydown={(e) => e.key === 'Escape' && closeModal()}
  >
    <div
      class="modal-content"
      role="dialog"
      aria-labelledby="modal-title"
      tabindex="0"
    >
      <div class="modal-header">
        <h2 id="modal-title" class="heading heading_2">Modal Title</h2>
        <button
          type="button"
          class="modal-close"
          onclick={closeModal}
          title="Close"
        >
          ×
        </button>
      </div>
      <div class="modal-body">
        <p>Content</p>
      </div>
      <div class="modal-footer">
        <button type="button" class="button button_secondary" onclick={closeModal}>
          Cancel
        </button>
        <button type="button" class="button button_green" onclick={handleSave}>
          Save
        </button>
      </div>
    </div>
  </div>
{/if}
```

**Critical modal requirements**:
- Overlay has `role="presentation"` (non-interactive backdrop)
- Overlay has `onclick={closeModal}` (click outside to close)
- Overlay has `onkeydown={...}` (Escape key to close)
- Dialog div has `role="dialog"` and `aria-labelledby="{heading-id}"`
- Dialog div has `tabindex="0"` (makes it keyboard-focusable)
- Dialog div has **NO onclick handler** (overlay already handles all clicks)
- Modal title (h2) has `id="modal-title"` (referenced by aria-labelledby)

### Rule 4: Never use self-closing non-void elements

❌ **WRONG**:
```svelte
<textarea id="story" bind:value={story} />
<input type="text" bind:value={name} />
```

✅ **CORRECT**:
```svelte
<textarea id="story" bind:value={story}></textarea>
<input type="text" bind:value={name} />
```

(Note: `<input>` is void and can self-close; `<textarea>` and other elements must close properly.)

### Rule 5: No inline styles for static properties

❌ **WRONG**:
```svelte
<div style="color: blue; margin: 10px; padding: 5px;">Text</div>
```

✅ **CORRECT** — use CSS classes from main.css only:
```svelte
<div class="text-blue spacing-lg">Text</div>
```

**Exception**: Dynamic styles like transform for modal positioning are allowed:
```svelte
<div class="modal-content" style="transform: translate({x}px, {y}px);">
  Draggable modal
</div>
```

### Rule 6: No page-scoped `<style>` blocks

❌ **WRONG**:
```svelte
<script>
  // ...
</script>

<div class="my-custom-div">Content</div>

<style>
  .my-custom-div { color: red; }
</style>
```

✅ **CORRECT** — add classes to `src/main.css` instead:
```svelte
<script>
  // ...
</script>

<div class="my-custom-div">Content</div>

<!-- No <style> block at all -->
```

Then in `src/main.css`:
```css
.my-custom-div { color: red; }
```

### Rule 7: Elements with mouse handlers need role attribute

❌ **WRONG** — mouse handler on div without role:
```svelte
<div onmousedown={startDrag}>Drag me</div>
```

✅ **CORRECT** — add role or use button:
```svelte
<div onmousedown={startDrag} role="button" tabindex="0">Drag me</div>

<!-- OR, better: use button if truly a button -->
<button type="button" onmousedown={startDrag}>Drag me</button>
```

## Pre-Commit Accessibility Checklist

Before committing any Svelte changes:

```bash
# 1. Type check (catches a11y violations)
npm run check

# 2. Build (full compilation test)
npm run build

# 3. Grep for common violations
grep -r "<div[^>]*onclick" src/routes --include="*.svelte"
grep -r "<textarea[^>]*/" src/routes --include="*.svelte"
grep -r "<style>" src/routes --include="*.svelte"
grep -r "style=\"" src/routes --include="*.svelte" | grep -v "transform"
```

**If ANY matches appear, FIX THEM before committing.**

## Standard Pattern for Each Entity

### File Structure
```
src/routes/{entity}/
  +page.svelte              # Index page (modified)
  [id]/
    +page.svelte            # View page (new)
    edit/
      +page.svelte          # Edit page (new)
```

### 1. View Page (`[id]/+page.svelte`)
Template structure:
- Import onMount and page store
- Fetch entity data on mount
- Display in entity-card with entity-view-header
- Green EDIT button navigates to `/entity/{id}/edit`
- Use detail-section, detail-row, detail-field classes

### 2. Edit Page (`[id]/edit/+page.svelte`)
Template structure:
- Import onMount and page store
- Load entity data and related entities (patterns for cards, etc.)
- Form sections with form-section class
- Form footer with form-footer class
- Cancel, Save buttons (and Edit Story/Markdown if applicable)
- Navigate to `/entity/view/{id}` on save
- Navigate back on cancel using history.back()

### 3. Index Page (`+page.svelte`)
Changes needed:
- Remove all edit/delete modals keeping only quick-add modal
- Quick-add modal: name + description only (+ required related entity select)
- Update handleCreate to navigate to new entity's view page
- Make table rows clickable: `onclick={() => navigateToCard(c.id)}`
- Update edit button: `onclick={(e) => handleEditClick(e, c.id)}`
- Remove all scoped :global() style definitions
- Keep only local component styles (card-header, sortable tables, etc.)

## Entity-Specific Notes

### Threats
- View page shows: Basic info, Threat metrics, STRIDE classification
- Edit page includes: All basic fields + STRIDE checkboxes
- Quick-add modal: name, description, only (advanced fields in edit)
- Existing threats/[threatId]/+page.svelte can be used as reference

### Assets, Countermeasures, Vulnerabilities
- Follow same pattern as threats
- View pages display relevant metrics
- Edit pages have all fields
- Quick-add modals simplified to essentials

## CSS Classes to Use

**From main.css:**
- `entity-card` - Main card container
- `entity-view-header` - Flexbox container with title and edit button
- `detail-section` - Section with h3 heading
- `detail-row` - Grid layout for detail fields
- `detail-field` - Individual field with label and value
- `detail-field.full` - Full width field (grid-column: 1 / -1)
- `form-section` - Form section container
- `form-footer` - Button footer (flex, justify-end)
- `button button_green` - Primary action button
- `button button_secondary` - Cancel button
- `modal-overlay`, `modal-content`, `modal-header`, `modal-body`, `modal-footer` - Modal elements

## Implementation Checklist

For each entity :

1. **Create view page**
   - [ ] Create `src/routes/{entity}/[id]/+page.svelte`
   - [ ] Copy pattern from patterns/[id]/+page.svelte
   - [ ] Customize entity-specific detail sections
   - [ ] Add green EDIT button

2. **Create edit page**
   - [ ] Create `src/routes/{entity}/[id]/edit/+page.svelte`
   - [ ] Copy pattern from patterns/[id]/edit/+page.svelte (or cards for related entity handling)
   - [ ] Implement form sections and footer
   - [ ] Add all entity fields to form
   - [ ] Implement handleSave and handleCancel

3. **Refactor index page**
   - [ ] Remove edit modal and any complex modals
   - [ ] Keep only quick-add modal (name, description, required selects)
   - [ ] Make table rows clickable
   - [ ] Update edit button to use handleEditClick
   - [ ] Remove all :global() style definitions
   - [ ] Keep only essential local styles

4. **Testing**
   - [ ] Verify TypeScript compilation (npm run check)
   - [ ] Test navigation (row click → view → edit → save/cancel)
   - [ ] Test quick-add modal
   - [ ] Verify CSS styling consistency


## Navigation Flow

Index Page (`+page.svelte`):
- Row click → `/{entity}/{id}` (view page)
- Pencil icon → `/{entity}/{id}/edit` (edit page)
- Add button → Quick-add modal

View Page (`[id]/+page.svelte`):
- EDIT button → `/{entity}/{id}/edit`
- (No breadcrumb, use sidebar to navigate back)

Edit Page (`[id]/edit/+page.svelte`):
- Save button → `/{entity}/{id}` (back to view)
- Cancel button → Back in history

## Commit Message Template

## Notes

- Do NOT create breadcrumb navigation - rely on sidebar
- All modals and forms use classes from main.css
- Entity names are displayed with `heading heading_3` class
- Detail sections use `detail-field` with label/p pair
- Always test with `npm run check` after changes
