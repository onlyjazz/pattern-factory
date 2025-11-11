<script lang="ts">
    import { onMount } from 'svelte';
    import { fetchDDTItems } from '$lib/api';
    import { selectedStudy } from '$lib/selectedStudy';

    let items: {item_id: string; description: string }[] = [];

    onMount(async () => {
        items = await fetchDDTItems();
        console.log("Fetched items:", items, items.length);
    });
</script>

<div class="page-title">
    <h1 class="heading_1">Data Dictionary</h1>
</div>

<div class="grid-col grid-col_24">
    <div class="studies card">
        <div class="grid-row">
            <div class="grid-col grid-col_12">
                <div class="heading heading_3">{$selectedStudy?.name}</div>
            </div>
        </div>
        <div class="table">
            <table>
                <thead>
                    <tr>
                        <th class="tal"><a href="#" class="table__sort">Variable</a></th>
                        <th class="tal"><a href="#" class="table__sort">Label</a></th>
                    </tr>
                </thead>
                <tbody>
                    {#each items as item}
                        <tr>
                            <td class="tal">{item.item_id}</td>
                            <td class="tal">{item.description}</td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    </div>
</div>

<style>
</style>