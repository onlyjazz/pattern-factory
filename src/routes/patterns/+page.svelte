<script lang="ts">
        import { onMount } from 'svelte';
        import { globalSearch } from '$lib/searchStore';
        import type { Pattern } from "$lib/db";
        
        let patterns: Pattern[] = [];
        let selectedKind = '';
        let loading = true;
        let error: string | null = null;
        let addModalError: string | null = null;
        
        let filteredPatterns: Pattern[] = [];
        let showAddModal = false;
        let newPattern: Partial<Pattern> = { name: '', description: '', kind: 'pattern' };
        const kinds = ['', 'pattern', 'anti-pattern'];
        
        let sortField: keyof Pattern | null = null;
        let sortDirection: 'asc' | 'desc' = 'asc';
        
        const apiBase = "http://localhost:8000";
        
        onMount(async () => {
                try {
                        const response = await fetch(`${apiBase}/patterns`);
                        if (!response.ok) throw new Error('Failed to fetch patterns');
                        const data = await response.json();
                        // Ensure all IDs are strings for consistent comparison
                        patterns = data.map((p: any) => ({ ...p, id: String(p.id) }));
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
					p.description.toLowerCase().includes($globalSearch.toLowerCase()) ||
					(p.taxonomy?.toLowerCase().includes($globalSearch.toLowerCase()) ?? false);
				const matchesKind = !selectedKind || p.kind === selectedKind;
				return matchesSearch && matchesKind;
			});
			sortPatterns();
		}
        
        function sortPatterns() {
                if (!sortField) return;
                filteredPatterns = [...filteredPatterns].sort((a, b) => {
                        const aVal = a[sortField] || '';
                        const bVal = b[sortField] || '';
                        const comparison = String(aVal).localeCompare(String(bVal));
                        return sortDirection === 'asc' ? comparison : -comparison;
                });
        }
        
        function toggleSort(field: keyof Pattern) {
                if (sortField === field) {
                        sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                        sortField = field;
                        sortDirection = 'asc';
                }
                sortPatterns();
        }
        
        $: if (patterns) filterPatterns();
        $: if ($globalSearch !== undefined) filterPatterns();
        $: if (selectedKind !== undefined) filterPatterns();
        
        function closeAddModal() {
                showAddModal = false;
                newPattern = { name: '', description: '', kind: 'pattern' };
                addModalError = null;
        }
        
        function navigateToPattern(patternId: string | number) {
                window.location.href = `/patterns/${patternId}`;
        }
        
        function handleEditClick(e: any, patternId: string | number) {
                e.stopPropagation();
                window.location.href = `/patterns/${patternId}/edit`;
        }
        
        async function handleCreate() {
                try {
                        addModalError = null;
                        if (!newPattern.name || !newPattern.description || !newPattern.kind) {
                                addModalError = 'Please fill in all fields';
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
                        patterns = [...patterns, { ...created, id: String(created.id) }];
                        filterPatterns();
                        closeAddModal();
                        // Navigate to the new pattern's view page
                        window.location.href = `/patterns/${created.id}`;
                } catch (e) {
                        addModalError = e instanceof Error ? e.message : 'Failed to create pattern';
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
                                <th class="tal sortable" class:sorted-asc={sortField === 'name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name' && sortDirection === 'desc'} onclick={() => toggleSort('name')}>
                                    Name
                                </th>
                                <th class="tal sortable" class:sorted-asc={sortField === 'description' && sortDirection === 'asc'} class:sorted-desc={sortField === 'description' && sortDirection === 'desc'} onclick={() => toggleSort('description')}>
                                    Description
                                </th>
                                <th class="tal sortable" class:sorted-asc={sortField === 'kind' && sortDirection === 'asc'} class:sorted-desc={sortField === 'kind' && sortDirection === 'desc'} onclick={() => toggleSort('kind')}>
                                    Kind
                                </th>
                                <th class="tal sortable" class:sorted-asc={sortField === 'taxonomy' && sortDirection === 'asc'} class:sorted-desc={sortField === 'taxonomy' && sortDirection === 'desc'} onclick={() => toggleSort('taxonomy')}>
                                    Taxonomy
                                </th>
                                <th class="tar">Actions</th>
                            </tr>
                        </thead>

                        <tbody>
								{#each filteredPatterns as p (p.id)}
								<tr class="pattern-row">
									<td class="tal"><a href="/patterns/story/{p.id}" class="story-link">{p.name}</a></td>
                                    <td class="tal">{p.description}</td>
                                    <td class="tal">{p.kind}</td>
                                    <td class="tal">{p.taxonomy || '-'}</td>

                                    <td class="tar">
                                        <button
                                            class="button button_small"
                                            onclick={(e) => handleEditClick(e, p.id)}
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
                {#if addModalError}
                    <div class="message message-error" style="margin-bottom: 20px;">Error: {addModalError}</div>
                {/if}
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

                    <div class="modal-footer">
                        <button
                            type="button"
                            class="button button_secondary"
                            onclick={closeAddModal}
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


<style>
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

    :global(.pattern-row) {
        transition: background-color 0.2s ease;
        cursor: pointer;
    }

    :global(.pattern-row:hover) {
        background-color: #f5f5f5;
    }

    th.sortable {
        cursor: pointer;
        user-select: none;
        position: relative;
    }

    th.sortable:hover {
        background-color: #f0f0f0;
    }

    th.sortable::after {
        content: ' ↕';
        opacity: 0.4;
        font-size: 0.85em;
    }

    th.sortable.sorted-asc::after {
        content: ' ▲';
        opacity: 1;
        color: #0066cc;
    }

    th.sortable.sorted-desc::after {
        content: ' ▼';
        opacity: 1;
        color: #0066cc;
    }
</style>

