<script lang="ts">
	import type { ProductOption } from '$lib/experiments';

	export let items: ProductOption[] = [];
	export let selectedIds: number[] = [];
	export let loading = false;

	let search = '';

	$: term = search.trim().toLowerCase();
	$: filtered = term
		? items.filter((item) => item.name.toLowerCase().includes(term))
		: items;

	function toggle(id: number) {
		selectedIds = selectedIds.includes(id)
			? selectedIds.filter((value) => value !== id)
			: [...selectedIds, id];
	}
</script>

<div class="multi-select">
	<div class="multi-select__search">
		<input
			type="text"
			class="input__text"
			placeholder="Search products..."
			bind:value={search}
		/>
	</div>
	{#if loading}
		<div class="multi-select__empty">Loading products...</div>
	{:else if filtered.length === 0}
		<div class="multi-select__empty">No products found</div>
	{:else}
		<div class="multi-select__list">
			{#each filtered as item (item.id)}
				<label class="multi-select__item">
					<input
						type="checkbox"
						class="checkbox-input checkbox-input_inline"
						checked={selectedIds.includes(item.id)}
						onchange={() => toggle(item.id)}
					/>
					<span>{item.name}</span>
				</label>
			{/each}
		</div>
	{/if}
	<p class="help-text">{selectedIds.length} product{selectedIds.length === 1 ? '' : 's'} selected</p>
</div>
