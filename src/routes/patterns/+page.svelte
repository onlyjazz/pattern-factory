<script lang="ts">
        import type { Pattern } from "$lib/db";
        
        let patterns: Pattern[] = []; // Initialize patterns array
        let searchInput = '';
        let selectedKind = '';
        
        let filteredPatterns: Pattern[] = [];
        let showAddModal = false;
        let showEditModal = false;
        let patternToEdit = {} as Pattern;
        let kinds = ['pattern', 'antipattern'];
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
                                </td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>


<style></style>

