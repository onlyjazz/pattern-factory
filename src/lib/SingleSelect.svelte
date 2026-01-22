<script lang="ts">
	import { onMount } from 'svelte';

	export interface SelectItem {
		id: string;
		name: string;
		description?: string;
	}

	export let items: SelectItem[] = [];
	export let selectedId: string | null = null;
	export let selectedName: string = '';
	export let placeholder: string = 'Search...';
	export let searchable: boolean = true;
	export let loading: boolean = false;

	let filteredItems: SelectItem[] = [];
	let searchValue: string = '';
	let showDropdown: boolean = false;

	$: if (items.length > 0 && filteredItems.length === 0) {
		filteredItems = items;
	}

	function handleSearch(value: string) {
		searchValue = value;
		if (!value) {
			filteredItems = items;
		} else {
			const lowerValue = value.toLowerCase();
			filteredItems = items.filter(
				(item) =>
					item.name.toLowerCase().includes(lowerValue) ||
					item.description?.toLowerCase().includes(lowerValue)
			);
		}
	}

	function handleSelect(item: SelectItem) {
		selectedId = item.id;
		selectedName = item.name;
		showDropdown = false;
		searchValue = '';
		filteredItems = items;
	}

	function handleClear() {
		selectedId = null;
		selectedName = '';
		searchValue = '';
		filteredItems = items;
		showDropdown = true;
	}

	function closeDropdown() {
		showDropdown = false;
	}
</script>

<div class="single-select">
	{#if selectedId}
		<div class="selected-item">
			<span class="selected-item-name">{selectedName}</span>
			<button class="action-button" onclick={() => handleClear()} type="button">
				Change
			</button>
		</div>
	{:else}
		<div class="search-section">
			<div class="search-input-wrapper">
				{#if searchable}
					<input
						type="text"
						class="input__text single-select-input"
						class:input__text_changed={searchValue?.length > 0}
						{placeholder}
						bind:value={searchValue}
						oninput={() => handleSearch(searchValue)}
						onfocus={() => (showDropdown = true)}
						onblur={() => setTimeout(closeDropdown, 200)}
					/>
				{/if}
			</div>
			{#if showDropdown}
				<div class="dropdown-list">
					{#if loading}
						<div class="dropdown-empty">Loading...</div>
					{:else if filteredItems.length === 0}
						<div class="dropdown-empty">No items found</div>
					{:else}
						{#each filteredItems as item}
							<button
								class="dropdown-item"
								onclick={() => handleSelect(item)}
								type="button"
							>
								<div class="dropdown-item-name">{item.name}</div>
								{#if item.description}
									<div class="dropdown-item-desc">{item.description}</div>
								{/if}
							</button>
						{/each}
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.single-select {
		width: 100%;
	}

	.selected-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		padding: 0;
		background: transparent;
		border: none;
	}

	.selected-item-name {
		flex: 1;
		padding: 8px 0;
		font-weight: 400;
		color: #333;
		font-size: 15px;
	}

	.action-button {
		padding: 4px 8px;
		background: transparent;
		border: 1px solid #ccc;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.8rem;
		white-space: nowrap;
		color: #666;
	}

	.action-button:hover {
		background: #f9f9f9;
		border-color: #999;
	}

	.search-section {
		position: relative;
		width: 100%;
	}

	.search-input-wrapper {
		position: relative;
	}

	:global(.single-select-input) {
		padding: 8px 12px !important;
		font-size: 1rem !important;
		min-height: 40px !important;
	}

	.dropdown-list {
		position: absolute;
		top: calc(100% - 1px);
		left: 0;
		right: 0;
		max-height: 300px;
		overflow-y: auto;
		background: white;
		border: 1px solid #ccc;
		border-radius: 0 0 4px 4px;
		box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
		z-index: 100;
	}

	.dropdown-empty {
		padding: 12px;
		text-align: center;
		color: #999;
		font-size: 0.875rem;
	}

	.dropdown-item {
		display: flex;
		flex-direction: column;
		padding: 12px;
		width: 100%;
		text-align: left;
		background: white;
		border: none;
		cursor: pointer;
		border-bottom: 1px solid #f0f0f0;
	}

	.dropdown-item:last-child {
		border-bottom: none;
	}

	.dropdown-item:hover {
		background: #f5f5f5;
	}

	.dropdown-item-name {
		font-weight: bold;
		color: #333;
		margin-bottom: 4px;
		font-size: 0.8em;
	}

	.dropdown-item-desc {
		font-size: 0.75rem;
		color: #999;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
