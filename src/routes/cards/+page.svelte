<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Card, Pattern } from '$lib/db';
	
	let cards: (Card & { pattern_name?: string })[] = [];
	let loading = true;
	let error: string | null = null;
	let addModalError: string | null = null;
	
	let filteredCards: (Card & { pattern_name?: string })[] = [];
	let showAddModal = false;
	let newCard: Partial<Card> = { 
		name: '', 
		description: ''
	};
	
	let sortField: keyof (Card & { pattern_name?: string }) | null = null;
	let sortDirection: 'asc' | 'desc' = 'asc';
	
	// Pattern search/autocomplete for add modal
	let patternSearchQuery = '';
	let patternSearchResults: Pattern[] = [];
	let selectedPatternId: number | null = null;
	let showPatternDropdown = false;
	
	const apiBase = 'http://localhost:8000';
	
	onMount(async () => {
		try {
			const response = await fetch(`${apiBase}/cards`);
			if (!response.ok) throw new Error('Failed to fetch cards');
			const data = await response.json();
			cards = data.map((c: any) => ({ ...c, id: String(c.id) }));
			filterCards();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});
	
	function filterCards() {
		filteredCards = cards.filter(c => {
			const matchesSearch = c.name.toLowerCase().includes($globalSearch.toLowerCase()) ||
				c.description.toLowerCase().includes($globalSearch.toLowerCase()) ||
				(c.pattern_name?.toLowerCase().includes($globalSearch.toLowerCase()) ?? false) ||
				(c.domain?.toLowerCase().includes($globalSearch.toLowerCase()) ?? false) ||
				(c.audience?.toLowerCase().includes($globalSearch.toLowerCase()) ?? false) ||
				(c.maturity?.toLowerCase().includes($globalSearch.toLowerCase()) ?? false);
			return matchesSearch;
		});
		sortCards();
	}
	
	function sortCards() {
		if (!sortField) return;
		filteredCards = [...filteredCards].sort((a, b) => {
			const aVal = a[sortField] || '';
			const bVal = b[sortField] || '';
			const comparison = String(aVal).localeCompare(String(bVal));
			return sortDirection === 'asc' ? comparison : -comparison;
		});
	}
	
	function toggleSort(field: keyof (Card & { pattern_name?: string })) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
		sortCards();
	}
	
	$: if (cards) filterCards();
	$: if ($globalSearch !== undefined) filterCards();
	
	async function searchPatterns(query: string, isEdit: boolean = false) {
		if (!query.trim()) {
			if (isEdit) {
				editPatternSearchResults = [];
			} else {
				patternSearchResults = [];
			}
			return;
		}
		
		try {
			const response = await fetch(`${apiBase}/patterns/search?q=${encodeURIComponent(query)}`);
			if (!response.ok) throw new Error('Failed to search patterns');
			const data = await response.json();
			if (isEdit) {
				editPatternSearchResults = data;
				editShowPatternDropdown = true;
			} else {
				patternSearchResults = data;
				showPatternDropdown = true;
			}
		} catch (e) {
			console.error('Pattern search error:', e);
		}
	}
	
	// @ts-ignore - Svelte 5 event handler typing
	function handlePatternSearchInput(e: any, isEdit: boolean) {
		const target = e.target as HTMLInputElement;
		searchPatterns(target.value, isEdit);
	}
	
	function selectPattern(pattern: Pattern) {
		selectedPatternId = pattern.id as any;
		patternSearchQuery = pattern.name;
		patternSearchResults = [];
		showPatternDropdown = false;
		newCard.pattern_id = pattern.id as any;
	}
	
	function closeAddModal() {
		showAddModal = false;
		newCard = { 
			name: '', 
			description: ''
		};
		selectedPatternId = null;
		patternSearchQuery = '';
		addModalError = null;
	}
	
	function navigateToCard(cardId: string | number) {
		window.location.href = `/cards/view/${cardId}`;
	}
	
	function handleEditClick(e: any, cardId: string | number) {
		e.stopPropagation();
		window.location.href = `/cards/${cardId}/edit`;
	}
	
	async function handleCreate() {
		try {
			addModalError = null;
			if (!newCard.name || !newCard.description || !selectedPatternId) {
				addModalError = 'Please fill in all required fields and select a pattern';
				return;
			}
			const response = await fetch(`${apiBase}/cards`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: newCard.name,
					description: newCard.description,
					pattern_id: selectedPatternId
				})
			});
			if (!response.ok) throw new Error('Failed to create card');
			const created = await response.json();
			cards = [...cards, { ...created, id: String(created.id) }];
			filterCards();
			closeAddModal();
			// Navigate to new card's view page
			window.location.href = `/cards/view/${created.id}`;
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create card';
		}
	}
	
</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Card
		</button>
		<h1 class="heading heading_1">Cards</h1>
	</div>

	<div class="grid-row">
		<!-- FULL WIDTH TABLE -->
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">Card Library</div>
				</div>

				{#if loading}
					<div class="message">Loading cards...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredCards.length === 0}
					<div class="message">No cards found</div>
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal sortable" class:sorted-asc={sortField === 'name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name' && sortDirection === 'desc'} onclick={() => toggleSort('name')}>
										Name
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'pattern_name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'pattern_name' && sortDirection === 'desc'} onclick={() => toggleSort('pattern_name')}>
										Pattern
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'order_index' && sortDirection === 'asc'} class:sorted-desc={sortField === 'order_index' && sortDirection === 'desc'} onclick={() => toggleSort('order_index')}>
										Order
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'domain' && sortDirection === 'asc'} class:sorted-desc={sortField === 'domain' && sortDirection === 'desc'} onclick={() => toggleSort('domain')}>
										Domain
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'audience' && sortDirection === 'asc'} class:sorted-desc={sortField === 'audience' && sortDirection === 'desc'} onclick={() => toggleSort('audience')}>
										Audience
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'maturity' && sortDirection === 'asc'} class:sorted-desc={sortField === 'maturity' && sortDirection === 'desc'} onclick={() => toggleSort('maturity')}>
										Maturity
									</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>

							<tbody>
								{#each filteredCards as c (c.id)}
								<tr class="card-row">
									<td class="tal"><a href="/cards/view/story/{c.id}" class="story-link">{c.name}</a></td>
										<td class="tal">{c.pattern_name || '-'}</td>
										<td class="tal">{c.order_index || '-'}</td>
										<td class="tal">{c.domain || '-'}</td>
										<td class="tal">{c.audience || '-'}</td>
										<td class="tal">{c.maturity || '-'}</td>
										<td class="tar">
											<button
												class="button button_small"
												onclick={(e) => handleEditClick(e, c.id)}
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
				<h2 id="add-modal-title" class="heading heading_2">Add Card</h2>
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
							bind:value={newCard.name}
							class="input__text"
							class:input__text_changed={newCard.name && newCard.name.length > 0}
							placeholder=""
							required
						/>
						<label for="add-name" class="input__label">Name</label>
					</div>

					<div class="input">
						<input
							id="add-description"
							type="text"
							bind:value={newCard.description}
							class="input__text"
							class:input__text_changed={newCard.description && newCard.description.length > 0}
							placeholder=""
							required
						/>
						<label for="add-description" class="input__label">Description</label>
					</div>

					<div class="input input_select">
						<div class="pattern-search-container">
							<input
								id="add-pattern-search"
								type="text"
								bind:value={patternSearchQuery}
								oninput={(e) => handlePatternSearchInput(e, false)}
								class="input__text input__text_changed"
								placeholder="Search patterns..."
								required
							/>
							<label for="add-pattern-search" class="input__label">Pattern</label>
							{#if showPatternDropdown && patternSearchResults.length > 0}
								<div class="pattern-dropdown">
									{#each patternSearchResults as pattern}
										<div class="pattern-option" onclick={() => selectPattern(pattern, false)}>
											<div class="pattern-name">{pattern.name}</div>
											<div class="pattern-description">{pattern.description}</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>
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

	:global(.card-row) {
		transition: background-color 0.2s ease;
		cursor: pointer;
	}

	:global(.card-row:hover) {
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

	.pattern-search-container {
		position: relative;
	}

	.pattern-dropdown {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		background: white;
		border: 1px solid #ddd;
		border-top: none;
		border-radius: 0 0 4px 4px;
		max-height: 200px;
		overflow-y: auto;
		z-index: 10;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
	}

	.pattern-option {
		padding: 10px 12px;
		cursor: pointer;
		border-bottom: 1px solid #f0f0f0;
	}

	.pattern-option:hover {
		background-color: #f5f5f5;
	}

	.pattern-name {
		font-weight: 500;
		color: #333;
		font-size: 14px;
	}

	.pattern-description {
		font-size: 12px;
		color: #666;
		margin-top: 4px;
	}
</style>
