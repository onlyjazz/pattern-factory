<script lang="ts">
	import { onMount } from 'svelte';

	interface Card {
		id: string;
		name: string;
		description?: string;
	}

	export let selectedCardId: string | null = null;
	export let selectedCardName: string = '';

	let cards: Card[] = [];
	let filteredCards: Card[] = [];
	let searchValue: string = '';
	let loading: boolean = false;
	let showDropdown: boolean = false;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			loading = true;
			const response = await fetch(`${apiBase}/cards`);
			if (!response.ok) throw new Error('Failed to fetch cards');
			cards = await response.json();
			filteredCards = cards;
		} catch (error) {
			console.error('Error fetching cards:', error);
		} finally {
			loading = false;
		}
	});

	function handleSearch(value: string) {
		searchValue = value;
		if (!value) {
			filteredCards = cards;
		} else {
			const lowerValue = value.toLowerCase();
			filteredCards = cards.filter(
				(card) =>
					card.name.toLowerCase().includes(lowerValue) ||
					card.description?.toLowerCase().includes(lowerValue)
			);
		}
	}

	function handleSelect(card: Card) {
		selectedCardId = card.id;
		selectedCardName = card.name;
		showDropdown = false;
		searchValue = '';
		filteredCards = cards;
	}

	function handleClear() {
		selectedCardId = null;
		selectedCardName = '';
		searchValue = '';
		filteredCards = cards;
		showDropdown = true;
	}

	function closeDropdown() {
		showDropdown = false;
	}
</script>

<div class="card-selector">
	{#if selectedCardId}
		<div class="selected-card">
			<span class="selected-card-name">{selectedCardName}</span>
			<button class="clear-button" onclick={() => handleClear()} type="button">
				Change
			</button>
		</div>
	{:else}
		<div class="search-section">
			<div class="search-input-wrapper">
				<input
					type="text"
					class="input__text card-search-input"
					class:input__text_changed={searchValue?.length > 0}
					placeholder="Search cards..."
					bind:value={searchValue}
					oninput={() => handleSearch(searchValue)}
					onfocus={() => (showDropdown = true)}
					onblur={() => setTimeout(closeDropdown, 200)}
				/>
			</div>
			{#if showDropdown}
				<div class="dropdown-list">
					{#if loading}
						<div class="dropdown-empty">Loading cards...</div>
					{:else if filteredCards.length === 0}
						<div class="dropdown-empty">No cards found</div>
					{:else}
						{#each filteredCards as card}
							<button
								class="dropdown-item"
								onclick={() => handleSelect(card)}
								type="button"
							>
								<div class="dropdown-item-name">{card.name}</div>
								{#if card.description}
									<div class="dropdown-item-desc">{card.description}</div>
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
	.card-selector {
		width: 100%;
	}

	.selected-card {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		padding: 0;
		background: transparent;
		border: none;
	}

	.selected-card-name {
		flex: 1;
		padding: 8px 0;
		font-weight: 400;
		color: #333;
		font-size: 15px;
	}

	.clear-button {
		padding: 4px 8px;
		background: transparent;
		border: 1px solid #ccc;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.8rem;
		white-space: nowrap;
		color: #666;
	}

	.clear-button:hover {
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

	:global(.card-search-input) {
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
