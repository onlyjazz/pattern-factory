<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import { modeStore } from '$lib/modeStore';
	import type { Threat, Card } from '$lib/db';
import { API_BASE } from '$lib/config';
	
	let threats: Threat[] = [];
	let cards: Card[] = [];
	let loading = true;
	let error: string | null = null;
	let editModalError: string | null = null;
	
	let filteredThreats: Threat[] = [];
	let activeModelId: number | null = null;
	
	let sortField: keyof Threat | null = 'tag';
	let sortDirection: 'asc' | 'desc' = 'asc';
	
	// Card search/autocomplete
	let cardSearchQuery = '';
	let cardSearchResults: Card[] = [];
	let selectedCardId: string | null = null;
	let showCardDropdown = false;
	
	// Edit mode card selection
	let editCardSearchQuery = '';
	let editCardSearchResults: Card[] = [];
	let editSelectedCardId: string | null = null;
	let editShowCardDropdown = false;
	
	const apiBase = API_BASE;
	
	$: filteredThreats = updateFilteredThreats(threats, $globalSearch, sortField, sortDirection);
	
onMount(async () => {
	const unsubscribe = modeStore.subscribe((state) => {
		activeModelId = state.activeModel;
	});
	
	try {
		const response = await fetch(`${apiBase}/threats`);
		if (!response.ok) throw new Error('Failed to fetch threats');
		const data = await response.json();
		threats = data.map((t: any) => ({ ...t, id: String(t.id) }));
	} catch (e) {
		error = e instanceof Error ? e.message : 'Unknown error';
	} finally {
		loading = false;
	}
	
	return unsubscribe;
});
	
function updateFilteredThreats(items: Threat[], search: string, field: keyof Threat | null, dir: 'asc' | 'desc'): Threat[] {
		let result = items;
		
		if (search.trim() !== '') {
			const term = search;
			result = result.filter(t => {
				const tag = (t.tag || '');
				const name = (t.name || '').toLowerCase();
				const description = (t.description || '');
				const domain = (t.domain || '');
				const probability = String(t.probability || '');
				const mitigationLevel = String(t.mitigation_level || '');
				const damageDescription = (t.damage_description || '');
				const disabled = String(t.disabled);
				return tag.includes(term) || name.includes(term.toLowerCase()) || description.includes(term) || domain.includes(term) || probability.includes(term) || mitigationLevel.includes(term) || damageDescription.includes(term) || disabled.includes(term);
			});
		}
		
		if (field) {
			result = [...result].sort((a, b) => {
				const aVal = a[field] || '';
				const bVal = b[field] || '';
				const comparison = String(aVal).localeCompare(String(bVal));
				return dir === 'asc' ? comparison : -comparison;
			});
		}
		
		return result;
	}
	
	function sortThreats() {
		if (!sortField) return;
		filteredThreats = [...filteredThreats].sort((a, b) => {
			const aVal = a[sortField] || '';
			const bVal = b[sortField] || '';
			const comparison = String(aVal).localeCompare(String(bVal));
			return sortDirection === 'asc' ? comparison : -comparison;
		});
	}
	
	function toggleSort(field: keyof Threat) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
		sortThreats();
	}
	

async function searchCards(query: string, isEdit: boolean = false) {
		if (!query.trim()) {
			if (isEdit) {
				editCardSearchResults = [];
			} else {
				cardSearchResults = [];
			}
			return;
		}
		
		try {
			const response = await fetch(`${apiBase}/cards`);
			if (!response.ok) throw new Error('Failed to fetch cards');
			const data = await response.json();
			const filtered = data.filter((c: any) => 
				c.name.toLowerCase().includes(query.toLowerCase()) ||
				c.description.toLowerCase().includes(query.toLowerCase())
			);
			if (isEdit) {
				editCardSearchResults = filtered;
				editShowCardDropdown = true;
			} else {
				cardSearchResults = filtered;
				showCardDropdown = true;
			}
		} catch (e) {
			console.error('Card search error:', e);
		}
	}
	
	// @ts-ignore - Svelte 5 event handler typing
	function handleCardSearchInput(e: any, isEdit: boolean) {
		const target = e.target as HTMLInputElement;
		searchCards(target.value, isEdit);
	}
	
	function toggleCard(card: Card, isEdit: boolean = false) {
		if (isEdit) {
			editSelectedCardId = editSelectedCardId === String(card.id) ? null : String(card.id);
		} else {
			selectedCardId = selectedCardId === String(card.id) ? null : String(card.id);
		}
	}
	
	async function handleSave(updatedThreat: Threat) {
		try {
			editModalError = null;
		const response = await fetch(`${apiBase}/threats/${updatedThreat.id}`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
				name: updatedThreat.name,
				description: updatedThreat.description,
				domain: updatedThreat.domain || null,
				tag: updatedThreat.tag || null,
				probability: updatedThreat.probability || null,
				damage_description: updatedThreat.damage_description || null,
				spoofing: updatedThreat.spoofing,
				tampering: updatedThreat.tampering,
				repudiation: updatedThreat.repudiation,
				information_disclosure: updatedThreat.information_disclosure,
				denial_of_service: updatedThreat.denial_of_service,
				elevation_of_privilege: updatedThreat.elevation_of_privilege,
				mitigation_level: updatedThreat.mitigation_level,
				disabled: updatedThreat.disabled,
				card_id: editSelectedCardId || null
			})
			});
			if (!response.ok) throw new Error('Failed to update threat');
		const updated = await response.json();
		threats = threats.map(t => t.id === String(updated.id) ? { ...updated, id: String(updated.id) } : t);
			closeEditModal();
		} catch (e) {
			editModalError = e instanceof Error ? e.message : 'Failed to save threat';
		}
	}
	
	
	async function handleDelete(threatId: string) {
		if (!confirm('Are you sure you want to delete this threat?')) return;
		
		try {
			const response = await fetch(`${apiBase}/threats/${threatId}`, {
				method: 'DELETE'
			});
			
		if (!response.ok) throw new Error('Failed to delete threat');
		threats = threats.filter(t => t.id !== threatId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete threat';
		}
	}

</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Threats</h1>
	</div>

	<div class="grid-row">
		<!-- FULL WIDTH TABLE -->
		<div class="grid-col grid-col_24">
			<div class="studies card">
			<div class="card-header">
			<div class="heading heading_3">Model threats</div>
				</div>

		{#if loading}
					<div class="message">Loading threats...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredThreats.length === 0}
					<div class="message">No threats found</div>
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal sortable" class:sorted-asc={sortField === 'tag' && sortDirection === 'asc'} class:sorted-desc={sortField === 'tag' && sortDirection === 'desc'} onclick={() => toggleSort('tag')}>
										Tag
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name' && sortDirection === 'desc'} onclick={() => toggleSort('name')}>
										Name
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'domain' && sortDirection === 'asc'} class:sorted-desc={sortField === 'domain' && sortDirection === 'desc'} onclick={() => toggleSort('domain')}>
										Domain
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'probability' && sortDirection === 'asc'} class:sorted-desc={sortField === 'probability' && sortDirection === 'desc'} onclick={() => toggleSort('probability')}>
										Probability
									</th>
							<th class="tal sortable" class:sorted-asc={sortField === 'description' && sortDirection === 'asc'} class:sorted-desc={sortField === 'description' && sortDirection === 'desc'} onclick={() => toggleSort('description')}>
									Description
							</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>

							<tbody>
								{#each filteredThreats as t (t.id)}
								<tr class="threat-row" onclick={() => window.location.href = `/threats/${t.id}`}>
									<td class="tal">{t.tag || '-'}</td>
									<td class="tal">{t.name}</td>
									<td class="tal">{t.domain || '-'}</td>
									<td class="tal">{t.probability || '-'}</td>
									<td class="tal">{t.description || '-'}</td>

									<td class="tar">
										<button
											class="button button_small"
											onclick={(e) => {
												e.stopPropagation();
												window.location.href = `/threats/${t.id}/edit`;
											}}
											title="Edit"
										>
											✎
										</button>
										<button
											class="button button_small"
											onclick={(e) => {
												e.stopPropagation();
												handleDelete(t.id);
											}}
											title="Delete"
										>
											🗑
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


<style>
	:global(.threat-row) {
		transition: background-color 0.2s ease;
		cursor: pointer;
	}

	:global(.threat-row:hover) {
		background-color: #f5f5f5;
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
		max-width: 600px;
		width: 90%;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
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
		overflow-y: auto;
		flex: 1;
		min-height: 0;
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
		padding: 20px;
		border-top: 1px solid #eee;
		flex-shrink: 0;
		background: white;
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

	:global(.threat-row:hover) {
		background-color: #f5f5f5;
	}

	:global(.threat-link) {
		color: #0066cc;
		text-decoration: none;
		cursor: pointer;
	}

	:global(.threat-link:hover) {
		text-decoration: underline;
	}

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

	.stride-checkboxes {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
		padding: 12px 0;
		border: 1px solid #ddd;
		border-radius: 4px;
		padding: 12px;
		background: #f9f9f9;
	}

	.checkbox-label {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		font-size: 14px;
		margin: 0;
	}

	.checkbox-label input[type="checkbox"] {
		cursor: pointer;
		width: 16px;
		height: 16px;
	}
</style>
