<script lang="ts">
        import { onMount } from 'svelte';
        import { globalSearch } from '$lib/searchStore';
        import type { Pattern } from "$lib/db";
        
        let patterns: Pattern[] = [];
        let selectedKind = '';
        let loading = true;
        let error: string | null = null;
        
        let filteredPatterns: Pattern[] = [];
        let showAddModal = false;
        let showEditModal = false;
        let patternToEdit = {} as Pattern;
        let newPattern: Partial<Pattern> = { name: '', description: '', kind: 'pattern' };
        const kinds = ['', 'pattern', 'anti-pattern'];
        
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
                                        kind: updatedPattern.kind
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
</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
<div class="page-title">
    <button class="button button_green" onclick={() => (showAddModal = true)}>
        Add Pattern
    </button>
    <h1 class="heading heading_1">Patterns</h1>
</div>

<div class="grid-row">
    <!-- FULL WIDTH TABLE -->
    <div class="grid-col grid-col_24">
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
                                <tr>
                                    <td class="tal">{p.name}</td>
                                    <td class="tal">{p.description}</td>
                                    <td class="tal">{p.kind}</td>

                                    <td class="tar">
                                        <button
                                            class="button button_small"
                                            onclick={() => handleEdit(p)}
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
                            class:input__text_changed={newPattern.name?.length > 0}
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
                            class:input__text_changed={newPattern.description?.length > 0}
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
</style>

