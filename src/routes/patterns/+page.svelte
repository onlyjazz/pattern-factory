<script lang="ts">
    import { onMount } from "svelte";
    import Modal from "$lib/Modal.svelte";
    import PatternEditor from "$lib/PatternEditor.svelte";
    import ActionMenu from "$lib/ActionMenu.svelte";

    import { patterns, type Pattern } from "$lib/stores/patterns";

    // --------------------------------------------------
    // State
    // --------------------------------------------------
    let showAddModal = $state(false);
    let showEditModal = $state(false);

    // Fresh pattern for Add modal
    let newPattern = $state({
        name: "",
        description: "",
        kind: ""
    });
    // Pattern being edited
    let patternToEdit: Pattern | null = $state(null);

    // --------------------------------------------------
    // Load patterns from backend
    // --------------------------------------------------
    onMount(async () => {
        await patterns.refresh();
    });

    // --------------------------------------------------
    // Actions
    // --------------------------------------------------
    function openEdit(p: Pattern) {
        patternToEdit = { ...p };
        showEditModal = true;
    }

    async function handleAddPattern(data: Pattern) {
        try {
            await patterns.addPattern(data);
            newPattern = { name: "", description: "", kind: "" };
            showAddModal = false;
        } catch (err) {
            console.error("Failed to add pattern:", err);
            alert("Could not save pattern.");
        }
    }

    async function handleEditPattern(updated: Pattern) {
        try {
            if (!patternToEdit?.id) return;
            await patterns.updatePattern(patternToEdit.id, updated);
            showEditModal = false;
        } catch (err) {
            console.error("Failed to update pattern:", err);
            alert("Could not update pattern.");
        }
    }

    async function handleDelete(id: number) {
        if (!confirm("Delete this pattern?")) return;
        await patterns.deletePattern(id);
    }

    // --------------------------------------------------
    // Search + Filter
    // --------------------------------------------------
    let searchInput = $state("");
    let selectedKind = $state("All");

    let kinds = $derived([
        "All",
        ...Array.from(new Set($patterns.map((p) => p.kind))).filter(Boolean)
    ]);

    let filteredPatterns = $derived(
        $patterns.filter((p) => {
            const matchesSearch =
                p.name.toLowerCase().includes(searchInput.toLowerCase()) ||
                p.description.toLowerCase().includes(searchInput.toLowerCase());

            const matchesKind =
                selectedKind === "All" ||
                p.kind.trim().toLowerCase() === selectedKind.trim().toLowerCase();

            return matchesSearch && matchesKind;
        })
    );
</script>

<!-- PAGE HEADER -->
<div class="page-title">
    <button class="button button_green" onclick={() => (showAddModal = true)}>
        Add Pattern
    </button>
    <h1 class="heading heading_1">Patterns</h1>
</div>

<div class="grid-row">
    <!-- LEFT FILTER PANEL -->
    <div class="grid-col grid-col_6">
        <div class="filters card">
            <div class="heading heading_3">Filters</div>

            <div class="input">
                <input
                    id="pattern-search"
                    bind:value={searchInput}
                    class="input__text"
                    class:input__text_changed={searchInput.length > 0}
                />
                <label class="input__label" for="pattern-search">Search patterns</label>
            </div>

            <div class="input input_select">
                <select
                    id="pattern-kind-filter"
                    bind:value={selectedKind}
                    class="input__text input__text_changed"
                >
                    {#each kinds as k}
                        <option>{k}</option>
                    {/each}
                </select>
                <label class="input__label" for="pattern-kind-filter">Kind</label>
            </div>
        </div>
    </div>

    <!-- RIGHT TABLE -->
    <div class="grid-col grid-col_18">
        <div class="studies card">
            <div class="heading heading_3">Pattern Library</div>

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
                        {#each filteredPatterns as p}
                            <tr>
                                <td class="tal">{p.name}</td>
                                <td class="tal">{p.description}</td>
                                <td class="tal">{p.kind}</td>

                                <td class="tar">
                                    <ActionMenu
                                        onEdit={() => openEdit(p)}
                                        onDelete={() => handleDelete(p.id!)}
                                    />
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- ADD PATTERN MODAL -->
<Modal bind:showModal={showAddModal}>
    {#snippet header()}
        <h2>Add Pattern</h2>
    {/snippet}
    {#snippet children()}
        <PatternEditor pattern={newPattern} onSave={handleAddPattern} />
    {/snippet}
</Modal>

<!-- EDIT PATTERN MODAL -->
<Modal bind:showModal={showEditModal}>
    {#snippet header()}
        <h2>Edit Pattern</h2>
    {/snippet}
    {#snippet children()}
        <PatternEditor pattern={patternToEdit} onSave={handleEditPattern} />
    {/snippet}
</Modal>

<style></style>
