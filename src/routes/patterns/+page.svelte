<script lang="ts">
        import { onMount } from 'svelte';
        import { globalSearch } from '$lib/searchStore';
        import type { Pattern } from "$lib/db";
        import { marked } from 'marked';
        
        let patterns: Pattern[] = [];
        let selectedKind = '';
        let loading = true;
        let error: string | null = null;
        
        let filteredPatterns: Pattern[] = [];
        let showAddModal = false;
        let showEditModal = false;
        let showStoryEditor = false;
        let viewingPatternId: string | null = null;
        let patternToEdit = {} as Pattern;
        let newPattern: Partial<Pattern> = { name: '', description: '', kind: 'pattern' };
        const kinds = ['', 'pattern', 'anti-pattern'];
        
        function getViewingPattern(): Pattern | undefined {
                return viewingPatternId ? patterns.find(p => p.id === viewingPatternId) : undefined;
        }
        
        const apiBase = "http://localhost:8000";
        
        onMount(async () => {
                try {
                        const response = await fetch(`${apiBase}/patterns`);
                        if (!response.ok) throw new Error('Failed to fetch patterns');
                        patterns = await response.json();
                        filterPatterns();
                } catch (e) {
                        error = e instanceof Error ? e.message : 'Unknown error';
                } finally {
                        loading = false;
                }
        });
        
        function filterPatterns() {
                filteredPatterns = patterns.filter(p => {
                        const matchesSearch = p.name.toLowerCase().includes($globalSearch.toLowerCase()) ||
                                p.description.toLowerCase().includes($globalSearch.toLowerCase());
                        const matchesKind = !selectedKind || p.kind === selectedKind;
                        return matchesSearch && matchesKind;
                });
        }
        
        $: if (patterns) filterPatterns();
        $: if ($globalSearch !== undefined) filterPatterns();
        $: if (selectedKind !== undefined) filterPatterns();
        
        function handleEdit(pattern: Pattern) {
                patternToEdit = { ...pattern };
                showEditModal = true;
        }
        
        function closeEditModal() {
                showEditModal = false;
                patternToEdit = {} as Pattern;
        }
        
        function closeAddModal() {
                showAddModal = false;
                newPattern = { name: '', description: '', kind: 'pattern' };
        }
        
        async function handleCreate() {
                try {
                        if (!newPattern.name || !newPattern.description || !newPattern.kind) {
                                error = 'Please fill in all fields';
                                return;
                        }
                        const response = await fetch(`${apiBase}/patterns`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                        name: newPattern.name,
                                        description: newPattern.description,
                                        kind: newPattern.kind
                                })
                        });
                        if (!response.ok) throw new Error('Failed to create pattern');
                        const created = await response.json();
                        patterns = [...patterns, created];
                        filterPatterns();
                        closeAddModal();
                } catch (e) {
                        error = e instanceof Error ? e.message : 'Failed to create pattern';
                }
        }
        
        async function handleSave(updatedPattern: Pattern) {
                try {
                        const response = await fetch(`${apiBase}/patterns/${updatedPattern.id}`, {
                                method: 'PUT',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                        name: updatedPattern.name,
                                        description: updatedPattern.description,
                                        kind: updatedPattern.kind,
                                        story_md: updatedPattern.story_md || null
                                })
                        });
                        if (!response.ok) throw new Error('Failed to update pattern');
                        const updated = await response.json();
                        patterns = patterns.map(p => p.id === updated.id ? updated : p);
                        filterPatterns();
                        closeEditModal();
                } catch (e) {
                        error = e instanceof Error ? e.message : 'Failed to save pattern';
                }
        }
        
        function openStoryEditor() {
                showStoryEditor = true;
        }
        
        function closeStoryEditor() {
                showStoryEditor = false;
        }
        
        function toggleStoryView(patternId: string) {
                viewingPatternId = viewingPatternId === patternId ? null : patternId;
        }
        
        $: viewingPattern = getViewingPattern();
</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
{#if viewingPatternId && viewingPattern}
    <div class="page-title">
        <h1 class="heading heading_1">{viewingPattern.name}</h1>
    </div>
{:else}
    <div class="page-title">
        <button class="button button_green" onclick={() => (showAddModal = true)}>
            Add Pattern
        </button>
        <h1 class="heading heading_1">Patterns</h1>
    </div>
{/if}

<div class="grid-row">
    <!-- FULL WIDTH TABLE -->
    <div class="grid-col grid-col_24">
        {#if viewingPatternId && viewingPattern}
            <!-- STORY VIEW -->
            <div class="studies card">
                <div class="story-view-content">
                    {@html marked(viewingPattern.story_md || '')}
                </div>
                <div class="story-view-footer">
                    <button
                        class="button button_secondary"
                        onclick={() => toggleStoryView(viewingPatternId || '')}
                    >
                        Back to Patterns
                    </button>
                    <button
                        class="button button_secondary"
                        onclick={() => handleEdit(viewingPattern)}
                    >
                        Edit
                    </button>
                </div>
            </div>
        {:else}
            <!-- PATTERNS TABLE VIEW -->
            <div class="studies card">
                <div class="card-header">
                    <div class="heading heading_3">Pattern Library</div>
                    <div class="kind-filter">
                        <select
                            id="pattern-kind-filter"
                            bind:value={selectedKind}
                            class="kind-filter-select"
                        >
                            {#each kinds as k}
                                <option value={k}>{k || 'All Kinds'}</option>
                            {/each}
                        </select>
                    </div>
                </div>

                {#if loading}
                    <div class="message">Loading patterns...</div>
                {:else if error}
                    <div class="message message-error">Error: {error}</div>
                {:else if filteredPatterns.length === 0}
                    <div class="message">No patterns found</div>
                {:else}
                    <div class="table">
                        <table>
                            <thead>
                                <tr>
                                    <th class="tal">Name</th>
                                    <th class="tal">Description</th>
                                    <th class="tal">Kind</th>
                                    <th class="tar">Actions</th>
                                </tr>
                            </thead>

                            <tbody>
                                {#each filteredPatterns as p (p.id)}
                                    <tr onclick={() => p.story_md && toggleStoryView(p.id)} class="pattern-row" class:has-story={p.story_md}>
                                        <td class="tal">{p.name}</td>
                                        <td class="tal">{p.description}</td>
                                        <td class="tal">{p.kind}</td>

                                        <td class="tar">
                                            <button
                                                class="button button_small"
                                                onclick={(e) => {
                                                    e.stopPropagation();
                                                    handleEdit(p);
                                                }}
                                                title="Edit"
                                            >
                                                ✎
                                            </button>
                                        </td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </div>
                {/if}
            </div>
        {/if}
    </div>
</div>
</div> <!-- end application-content-area -->

<!-- EDIT MODAL -->
{#if showEditModal && Object.keys(patternToEdit).length > 0}
    <div class="modal-overlay" onclick={closeEditModal}>
        <div class="modal-content" role="dialog" aria-labelledby="edit-modal-title" onclick={(e) => e.stopPropagation()}>
            <div class="modal-header">
                <h2 id="edit-modal-title" class="heading heading_2">Edit Pattern</h2>
                <button
                    class="modal-close"
                    onclick={closeEditModal}
                    title="Close"
                >
                    ×
                </button>
            </div>

            <div class="modal-body">
                <form onsubmit={(e) => {
                    e.preventDefault();
                    handleSave(patternToEdit);
                }}>
                    <div class="input">
                        <input
                            id="edit-name"
                            type="text"
                            bind:value={patternToEdit.name}
                            class="input__text"
                            class:input__text_changed={patternToEdit.name?.length > 0}
                            required
                        />
                        <label for="edit-name" class="input__label">Name</label>
                    </div>

                    <div class="input">
                        <input
                            id="edit-description"
                            type="text"
                            bind:value={patternToEdit.description}
                            class="input__text"
                            class:input__text_changed={patternToEdit.description?.length > 0}
                            required
                        />
                        <label for="edit-description" class="input__label">Description</label>
                    </div>

                    <div class="input input_select">
                        <select
                            id="edit-kind"
                            bind:value={patternToEdit.kind}
                            class="input__text input__text_changed"
                            required
                        >
                            <option value="pattern">Pattern</option>
                            <option value="anti-pattern">Anti-Pattern</option>
                        </select>
                        <label for="edit-kind" class="input__label">Kind</label>
                    </div>

                    <div class="modal-footer">
                        <button
                            type="button"
                            class="button button_secondary"
                            onclick={closeEditModal}
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            class="button button_secondary"
                            onclick={openStoryEditor}
                        >
                            Edit Story
                        </button>
                        <button type="submit" class="button button_green">
                            Save
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
{/if}

<!-- ADD MODAL -->
{#if showAddModal}
    <div class="modal-overlay" onclick={closeAddModal}>
        <div class="modal-content" role="dialog" aria-labelledby="add-modal-title" onclick={(e) => e.stopPropagation()}>
            <div class="modal-header">
                <h2 id="add-modal-title" class="heading heading_2">Add Pattern</h2>
                <button
                    class="modal-close"
                    onclick={closeAddModal}
                    title="Close"
                >
                    ×
                </button>
            </div>

            <div class="modal-body">
                <form onsubmit={(e) => {
                    e.preventDefault();
                    handleCreate();
                }}>
                    <div class="input">
                        <input
                            id="add-name"
                            type="text"
                            bind:value={newPattern.name}
                            class="input__text"
                            class:input__text_changed={newPattern.name && newPattern.name.length > 0}
                            placeholder=""
                            required
                        />
                        <label for="add-name" class="input__label">Name</label>
                    </div>

                    <div class="input">
                        <input
                            id="add-description"
                            type="text"
                            bind:value={newPattern.description}
                            class="input__text"
                            class:input__text_changed={newPattern.description && newPattern.description.length > 0}
                            placeholder=""
                            required
                        />
                        <label for="add-description" class="input__label">Description</label>
                    </div>

                    <div class="input input_select">
                        <select
                            id="add-kind"
                            bind:value={newPattern.kind}
                            class="input__text input__text_changed"
                            required
                        >
                            <option value="pattern">Pattern</option>
                            <option value="anti-pattern">Anti-Pattern</option>
                        </select>
                        <label for="add-kind" class="input__label">Kind</label>
                    </div>

                    <div class="modal-footer">
                        <button
                            type="button"
                            class="button button_secondary"
                            onclick={closeAddModal}
                        >
                            Cancel
                        </button>
                        <button type="submit" class="button button_green">
                            Create
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
{/if}

<!-- STORY EDITOR MODAL -->
{#if showStoryEditor && Object.keys(patternToEdit).length > 0}
    <div class="modal-overlay" onclick={closeStoryEditor}>
        <div class="story-editor-content" role="dialog" aria-labelledby="story-editor-title" onclick={(e) => e.stopPropagation()}>
            <div class="modal-header">
                <h2 id="story-editor-title" class="heading heading_2">Edit Story: {patternToEdit.name}</h2>
                <button
                    class="modal-close"
                    onclick={closeStoryEditor}
                    title="Close"
                >
                    ×
                </button>
            </div>

            <div class="story-editor-body">
                <div class="story-editor-editor">
                    <textarea
                        id="story-editor-textarea"
                        bind:value={patternToEdit.story_md}
                        class="story-editor-textarea"
                        placeholder="Enter your story in Markdown format..."
                    ></textarea>
                </div>
                <div class="story-editor-preview">
                    <div class="preview-label">Preview</div>
                    <div class="story-editor-preview-content">
                        {@html marked(patternToEdit.story_md || '')}
                    </div>
                </div>
            </div>

            <div class="modal-footer">
                <button
                    type="button"
                    class="button button_secondary"
                    onclick={closeStoryEditor}
                >
                    Done
                </button>
            </div>
        </div>
    </div>
{/if}

<style>
    :global(.button_small) {
        background: none !important;
        border: none !important;
        padding: 4px 8px !important;
        cursor: pointer !important;
        font-size: 18px !important;
        color: #666 !important;
        vertical-align: top !important;
        line-height: 1 !important;
        box-shadow: none !important;
    }

    :global(.button_small:hover) {
        color: #333 !important;
        background: none !important;
    }

    :global(td.tar button) {
        background: none !important;
        border: none !important;
    }

    :global(td.tar) {
        vertical-align: top;
    }

    :global(.modal-overlay) {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
    }

    :global(.modal-content) {
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        max-width: 500px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
    }

    :global(.modal-header) {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px;
        border-bottom: 1px solid #eee;
    }

    :global(.modal-close) {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #666;
        padding: 0;
        width: 30px;
        height: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    :global(.modal-close:hover) {
        color: #333;
    }

    :global(.modal-body) {
        padding: 20px;
    }

    :global(.modal-body form) {
        display: flex;
        flex-direction: column;
        gap: 20px;
    }

    :global(.modal-footer) {
        display: flex;
        gap: 10px;
        justify-content: flex-end;
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid #eee;
    }

    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }

    .kind-filter {
        flex-shrink: 0;
    }

    .kind-filter-select {
        padding: 0.5rem 0.75rem;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        background-color: white;
        font-size: 0.875rem;
        font-family: 'Roboto', system-ui, -apple-system, sans-serif;
        color: #495057;
        cursor: pointer;
    }

    .kind-filter-select:hover {
        border-color: #adb5bd;
        background-color: #f8f9fa;
    }

    .kind-filter-select:focus {
        outline: none;
        border-color: #adb5bd;
    }

    :global(.story-editor-content) {
        background: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        max-width: 1000px;
        width: 90%;
        max-height: 85vh;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }

    :global(.story-editor-body) {
        display: flex;
        gap: 15px;
        padding: 20px;
        flex: 1;
        min-height: 0;
    }

    :global(.story-editor-editor) {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-width: 0;
    }

    :global(.story-editor-textarea) {
        flex: 1;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 4px;
        font-family: 'Monaco', 'Courier New', monospace;
        font-size: 14px;
        resize: none;
        width: 100%;
    }

    :global(.story-editor-textarea:focus) {
        outline: none;
        border-color: #999;
    }

    :global(.story-editor-preview) {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-width: 0;
        border: 1px solid #ddd;
        border-radius: 4px;
        background: #f9f9f9;
    }

    :global(.preview-label) {
        padding: 8px 10px;
        font-size: 12px;
        font-weight: bold;
        color: #666;
        border-bottom: 1px solid #ddd;
        background: #f0f0f0;
    }

    :global(.story-editor-preview-content) {
        flex: 1;
        overflow-y: auto;
        padding: 10px;
        font-size: 14px;
        line-height: 1.5;
    }

    :global(.story-editor-preview-content h1) {
        font-size: 24px;
        font-weight: bold;
        margin: 15px 0 10px 0;
    }

    :global(.story-editor-preview-content h2) {
        font-size: 20px;
        font-weight: bold;
        margin: 12px 0 8px 0;
    }

    :global(.story-editor-preview-content h3) {
        font-size: 16px;
        font-weight: bold;
        margin: 10px 0 6px 0;
    }

    :global(.story-editor-preview-content p) {
        margin: 8px 0;
    }

    :global(.story-editor-preview-content ul),
    :global(.story-editor-preview-content ol) {
        margin: 8px 0 8px 20px;
    }

    :global(.story-editor-preview-content li) {
        margin: 4px 0;
    }

    :global(.story-editor-preview-content code) {
        background: #e0e0e0;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Monaco', 'Courier New', monospace;
        font-size: 12px;
    }

    :global(.story-editor-preview-content blockquote) {
        border-left: 4px solid #ccc;
        padding-left: 10px;
        margin: 8px 0;
        color: #666;
        font-style: italic;
    }

    :global(.pattern-row) {
        transition: background-color 0.2s ease;
    }

    :global(.pattern-row.has-story) {
        cursor: pointer;
    }

    :global(.pattern-row.has-story:hover) {
        background-color: #f5f5f5;
    }

    .story-view-content {
        padding: 20px;
        font-size: 15px;
        line-height: 1.7;
        color: #495057;
    }

    .story-view-content :global(h1) {
        font-size: 24px;
        font-weight: 600;
        margin: 20px 0 12px 0;
    }

    .story-view-content :global(h2) {
        font-size: 20px;
        font-weight: 600;
        margin: 16px 0 10px 0;
    }

    .story-view-content :global(h3) {
        font-size: 16px;
        font-weight: 600;
        margin: 12px 0 8px 0;
    }

    .story-view-content :global(p) {
        margin: 10px 0;
    }

    .story-view-content :global(ul),
    .story-view-content :global(ol) {
        margin: 10px 0 10px 25px;
    }

    .story-view-content :global(li) {
        margin: 5px 0;
    }

    .story-view-content :global(code) {
        background: #f0f0f0;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: 'Monaco', 'Courier New', monospace;
        font-size: 13px;
        color: #d63384;
    }

    .story-view-content :global(pre) {
        background: #f5f5f5;
        padding: 12px;
        border-radius: 4px;
        overflow-x: auto;
        margin: 10px 0;
        font-size: 13px;
    }

    .story-view-content :global(blockquote) {
        border-left: 4px solid #dee2e6;
        padding-left: 15px;
        margin: 12px 0;
        color: #6c757d;
        font-style: italic;
    }

    .story-view-content :global(strong) {
        font-weight: 600;
    }

    .story-view-content :global(em) {
        font-style: italic;
    }

    .story-view-footer {
        display: flex;
        gap: 10px;
        justify-content: flex-end;
        padding: 15px 20px;
        border-top: 1px solid #dee2e6;
        background-color: #f8f9fa;
    }
</style>

