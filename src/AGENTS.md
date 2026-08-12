# Consistent UI Refactoring - Implementation Guide

## Never do this
Never add a click event to a non-interactive element (like a div or span), which prevents keyboard-only users from triggering it. Replace the element with a <button type="button">
This clutters up the log file with unnecessary information a11y warnings

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

Index Page:
- Row click → `/entity/view/{id}`
- Pencil icon → `/entity/{id}/edit`
- Add button → Quick-add modal

View Page:
- EDIT button → `/entity/{id}/edit`
- (No breadcrumb, use sidebar to navigate back)

Edit Page:
- Save button → `/entity/view/{id}`
- Cancel button → Back in history

## Commit Message Template

## Notes

- Do NOT create breadcrumb navigation - rely on sidebar
- All modals and forms use classes from main.css
- Entity names are displayed with `heading heading_3` class
- Detail sections use `detail-field` with label/p pair
- Always test with `npm run check` after changes
