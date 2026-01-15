<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Card, Pattern } from '$lib/db';
	import { marked } from 'marked';
	
	let cards: (Card & { pattern_name?: string })[] = [];
	let patterns: Pattern[] = [];
	let loading = true;
	let error: string | null = null;
	let addModalError: string | null = null;
	let editModalError: string | null = null;
	
	let filteredCards: (Card & { pattern_name?: string })[] = [];
	let showAddModal = false;
	let showEditModal = false;
	let showMarkdownEditor = false;
	let cardToEdit = {} as Card & { pattern_name?: string };
	let newCard: Partial<Card> = { 
		name: '', 
		description: '', 
		order_index: 0,
		domain: '',
		audience: '',
		maturity: ''
	};
	
	let sortField: keyof (Card & { pattern_name?: string }) | null = null;
	let sortDirection: 'asc' | 'desc' = 'asc';
	
	// Pattern search/autocomplete
	let patternSearchQuery = '';
	let patternSearchResults: Pattern[] = [];
	let selectedPatternId: number | null = null;
	let selectedPatternName: string = '';
	let showPatternDropdown = false;
	
	let editPatternSearchQuery = '';
	let editPatternSearchResults: Pattern[] = [];
	let editSelectedPatternId: number | null = null;
	let editSelectedPatternName: string = '';
	let editShowPatternDropdown = false;
	
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
	
	function selectPattern(pattern: Pattern, isEdit: boolean = false) {
		if (isEdit) {
			editSelectedPatternId = pattern.id as any;
			editSelectedPatternName = pattern.name;
			editPatternSearchQuery = pattern.name;
			editPatternSearchResults = [];
			editShowPatternDropdown = false;
			cardToEdit.pattern_id = pattern.id as any;
		} else {
			selectedPatternId = pattern.id as any;
			selectedPatternName = pattern.name;
			patternSearchQuery = pattern.name;
			patternSearchResults = [];
			showPatternDropdown = false;
			newCard.pattern_id = pattern.id as any;
		}
	}
	
	function handleEdit(card: Card & { pattern_name?: string }) {
		cardToEdit = { ...card };
		editSelectedPatternId = card.pattern_id;
		editSelectedPatternName = card.pattern_name || '';
		editPatternSearchQuery = card.pattern_name || '';
		showEditModal = true;
	}
	
	function closeEditModal() {
		showEditModal = false;
		cardToEdit = {} as Card & { pattern_name?: string };
		editSelectedPatternId = null;
		editSelectedPatternName = '';
		editPatternSearchQuery = '';
		editModalError = null;
	}
	
	function closeAddModal() {
		showAddModal = false;
		newCard = { 
			name: '', 
			description: '', 
			order_index: 0,
			domain: '',
			audience: '',
			maturity: ''
		};
		selectedPatternId = null;
		selectedPatternName = '';
		patternSearchQuery = '';
		addModalError = null;
	}
	
	function closeMarkdownEditor() {
		showMarkdownEditor = false;
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
					pattern_id: selectedPatternId,
					markdown: newCard.markdown || null,
					order_index: newCard.order_index || 0,
					domain: newCard.domain || null,
					audience: newCard.audience || null,
					maturity: newCard.maturity || null
				})
			});
			if (!response.ok) throw new Error('Failed to create card');
			const created = await response.json();
			cards = [...cards, { ...created, id: String(created.id), pattern_name: selectedPatternName }];
			filterCards();
			closeAddModal();
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create card';
		}
	}
	
	async function handleSave(updatedCard: Card & { pattern_name?: string }) {
		try {
			editModalError = null;
			if (!editSelectedPatternId) {
				editModalError = 'Please select a pattern';
				return;
			}
			const response = await fetch(`${apiBase}/cards/${updatedCard.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: updatedCard.name,
					description: updatedCard.description,
					pattern_id: editSelectedPatternId,
					markdown: updatedCard.markdown || null,
					order_index: updatedCard.order_index || 0,
					domain: updatedCard.domain || null,
					audience: updatedCard.audience || null,
					maturity: updatedCard.maturity || null
				})
			});
			if (!response.ok) throw new Error('Failed to update card');
			const updated = await response.json();
			cards = cards.map(c => c.id === String(updated.id) ? { ...updated, id: String(updated.id), pattern_name: editSelectedPatternName } : c);
			filterCards();
			closeEditModal();
		} catch (e) {
			editModalError = e instanceof Error ? e.message : 'Failed to save card';
		}
	}
	
	function openMarkdownEditor() {
		showMarkdownEditor = true;
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
									<tr class="card-row" class:has-markdown={c.markdown && c.markdown !== '#Pattern card'}>
										<td class="tal">
											{#if c.markdown && c.markdown !== '#Pattern card'}
												<a href="/cards/{c.id}" class="card-link">{c.name}</a>
											{:else}
												{c.name}
											{/if}
										</td>
										<td class="tal">{c.pattern_name || '-'}</td>
										<td class="tal">{c.order_index || '-'}</td>
										<td class="tal">{c.domain || '-'}</td>
										<td class="tal">{c.audience || '-'}</td>
										<td class="tal">{c.maturity || '-'}</td>
										<td class="tar">
											<button
												class="button button_small"
												onclick={(e) => {
													e.stopPropagation();
													handleEdit(c);
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
		</div>
	</div>
</div> <!-- end application-content-area -->

<!-- EDIT MODAL -->
{#if showEditModal && Object.keys(cardToEdit).length > 0}
	<div class="modal-overlay" onclick={closeEditModal}>
		<div class="modal-content" role="dialog" aria-labelledby="edit-modal-title" onclick={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2 id="edit-modal-title" class="heading heading_2">Edit Card</h2>
				<button
					class="modal-close"
					onclick={closeEditModal}
					title="Close"
				>
					×
				</button>
			</div>

			<div class="modal-body">
				{#if editModalError}
					<div class="message message-error" style="margin-bottom: 20px;">Error: {editModalError}</div>
				{/if}
				<form onsubmit={(e) => {
					e.preventDefault();
					handleSave(cardToEdit);
				}}>
					<div class="input">
						<input
							id="edit-name"
							type="text"
							bind:value={cardToEdit.name}
							class="input__text"
							class:input__text_changed={cardToEdit.name?.length > 0}
							required
						/>
						<label for="edit-name" class="input__label">Name</label>
					</div>

					<div class="input">
						<input
							id="edit-description"
							type="text"
							bind:value={cardToEdit.description}
							class="input__text"
							class:input__text_changed={cardToEdit.description?.length > 0}
							required
						/>
						<label for="edit-description" class="input__label">Description</label>
					</div>

					<div class="input input_select">
						<div class="pattern-search-container">
							<input
								id="edit-pattern-search"
								type="text"
								bind:value={editPatternSearchQuery}
								oninput={(e) => handlePatternSearchInput(e, true)}
								class="input__text input__text_changed"
								placeholder="Search patterns..."
								required
							/>
							<label for="edit-pattern-search" class="input__label">Pattern</label>
							{#if editShowPatternDropdown && editPatternSearchResults.length > 0}
								<div class="pattern-dropdown">
									{#each editPatternSearchResults as pattern}
										<div class="pattern-option" onclick={() => selectPattern(pattern, true)}>
											<div class="pattern-name">{pattern.name}</div>
											<div class="pattern-description">{pattern.description}</div>
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</div>

					<div class="input">
						<input
							id="edit-order-index"
							type="number"
							bind:value={cardToEdit.order_index}
							class="input__text"
							class:input__text_changed={cardToEdit.order_index}
						/>
						<label for="edit-order-index" class="input__label">Order Index</label>
					</div>

					<div class="input">
						<input
							id="edit-domain"
							type="text"
							bind:value={cardToEdit.domain}
							class="input__text"
							class:input__text_changed={cardToEdit.domain?.length > 0}
						/>
						<label for="edit-domain" class="input__label">Domain</label>
					</div>

					<div class="input">
						<input
							id="edit-audience"
							type="text"
							bind:value={cardToEdit.audience}
							class="input__text"
							class:input__text_changed={cardToEdit.audience?.length > 0}
						/>
						<label for="edit-audience" class="input__label">Audience</label>
					</div>

					<div class="input">
						<input
							id="edit-maturity"
							type="text"
							bind:value={cardToEdit.maturity}
							class="input__text"
							class:input__text_changed={cardToEdit.maturity?.length > 0}
						/>
						<label for="edit-maturity" class="input__label">Maturity</label>
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
							onclick={openMarkdownEditor}
						>
							Edit Markdown
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

					<div class="input">
						<input
							id="add-order-index"
							type="number"
							bind:value={newCard.order_index}
							class="input__text"
						/>
						<label for="add-order-index" class="input__label">Order Index</label>
					</div>

					<div class="input">
						<input
							id="add-domain"
							type="text"
							bind:value={newCard.domain}
							class="input__text"
							class:input__text_changed={newCard.domain && newCard.domain.length > 0}
						/>
						<label for="add-domain" class="input__label">Domain</label>
					</div>

					<div class="input">
						<input
							id="add-audience"
							type="text"
							bind:value={newCard.audience}
							class="input__text"
							class:input__text_changed={newCard.audience && newCard.audience.length > 0}
						/>
						<label for="add-audience" class="input__label">Audience</label>
					</div>

					<div class="input">
						<input
							id="add-maturity"
							type="text"
							bind:value={newCard.maturity}
							class="input__text"
							class:input__text_changed={newCard.maturity && newCard.maturity.length > 0}
						/>
						<label for="add-maturity" class="input__label">Maturity</label>
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

<!-- MARKDOWN EDITOR MODAL -->
{#if showMarkdownEditor && Object.keys(cardToEdit).length > 0}
	<div class="modal-overlay" onclick={closeMarkdownEditor}>
		<div class="story-editor-content" role="dialog" aria-labelledby="markdown-editor-title" onclick={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2 id="markdown-editor-title" class="heading heading_2">Edit Markdown: {cardToEdit.name}</h2>
				<button
					class="modal-close"
					onclick={closeMarkdownEditor}
					title="Close"
				>
					×
				</button>
			</div>

			<div class="story-editor-body">
				<div class="story-editor-editor">
					<textarea
						id="markdown-editor-textarea"
						bind:value={cardToEdit.markdown}
						class="story-editor-textarea"
						placeholder="Enter your card markdown..."
					></textarea>
				</div>
				<div class="story-editor-preview">
					<div class="preview-label">Preview</div>
					<div class="story-editor-preview-content">
						{@html marked(cardToEdit.markdown || '')}
					</div>
				</div>
			</div>

			<div class="modal-footer">
				<button
					type="button"
					class="button button_secondary"
					onclick={closeMarkdownEditor}
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
		margin-right: 0.5rem;
	}

	:global(.button_small:hover) {
		color: #333 !important;
		background: none !important;
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

	:global(.card-row) {
		transition: background-color 0.2s ease;
	}

	:global(.card-row.has-markdown:hover) {
		background-color: #f5f5f5;
	}

	:global(.card-link) {
		color: #0066cc;
		text-decoration: none;
		cursor: pointer;
	}

	:global(.card-link:hover) {
		text-decoration: underline;
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
