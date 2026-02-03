<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import { modeStore } from '$lib/modeStore';
	import type { Asset } from '$lib/db';
	
	let assets: Asset[] = [];
	let loading = true;
	let error: string | null = null;
	let addModalError: string | null = null;
	
	let filteredAssets: Asset[] = [];
	let showAddModal = false;
	let activeModelId: number | null = null;
	let newAsset: Partial<Asset> = { 
		name: '', 
		description: ''
	};
	
	let sortField: keyof Asset | null = 'tag';
	let sortDirection: 'asc' | 'desc' = 'asc';
	
	const apiBase = 'http://localhost:8000';
	
	onMount(async () => {
		const unsubscribe = modeStore.subscribe((state) => {
			activeModelId = state.activeModel;
		});
		
		try {
			const response = await fetch(`${apiBase}/assets`);
			if (!response.ok) throw new Error('Failed to fetch assets');
			const data = await response.json();
			assets = data.map((a: any) => ({ ...a, id: String(a.id) }));
			filterAssets();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
		
		return unsubscribe;
	});
	
	function filterAssets() {
		filteredAssets = assets.filter(a => {
			const matchesSearch = a.name.toLowerCase().includes($globalSearch.toLowerCase()) ||
				a.description.toLowerCase().includes($globalSearch.toLowerCase());
			return matchesSearch;
		});
		sortAssets();
	}
	
	function sortAssets() {
		if (!sortField) return;
		filteredAssets = [...filteredAssets].sort((a, b) => {
			const aVal = a[sortField] || '';
			const bVal = b[sortField] || '';
			const comparison = String(aVal).localeCompare(String(bVal));
			return sortDirection === 'asc' ? comparison : -comparison;
		});
	}
	
	function toggleSort(field: keyof Asset) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
		sortAssets();
	}
	
	$: if (assets) filterAssets();
	$: if ($globalSearch !== undefined) filterAssets();
	
	function closeAddModal() {
		showAddModal = false;
		newAsset = { 
			name: '', 
			description: ''
		};
		addModalError = null;
	}
	
	async function handleCreate() {
		try {
			addModalError = null;
			if (!newAsset.name || !newAsset.description) {
				addModalError = 'Please fill in all required fields';
				return;
			}
			const response = await fetch(`${apiBase}/assets`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: newAsset.name,
					description: newAsset.description,
					fixed_value: newAsset.fixed_value || 0,
					disabled: newAsset.disabled || false,
					model_id: activeModelId || 1,
				})
			});
			if (!response.ok) throw new Error('Failed to create asset');
			const created = await response.json();
			assets = [...assets, { ...created, id: String(created.id) }];
			filterAssets();
			closeAddModal();
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create asset';
		}
	}
	
	async function handleDelete(assetId: string) {
		if (!confirm('Are you sure you want to delete this asset?')) return;
		
		try {
			const response = await fetch(`${apiBase}/assets/${assetId}`, {
				method: 'DELETE'
			});
			
			if (!response.ok) throw new Error('Failed to delete asset');
			assets = assets.filter(a => a.id !== assetId);
			filterAssets();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete asset';
		}
	}

</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Asset
		</button>
		<h1 class="heading heading_1">Assets</h1>
	</div>

	<div class="grid-row">
		<!-- FULL WIDTH TABLE -->
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">Model assets</div>
				</div>

				{#if loading}
					<div class="message">Loading assets...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredAssets.length === 0}
					<div class="message">No assets found</div>
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
							<th class="tal sortable" class:sorted-asc={sortField === 'description' && sortDirection === 'asc'} class:sorted-desc={sortField === 'description' && sortDirection === 'desc'} onclick={() => toggleSort('description')}>
								Description
							</th>
							<th class="tal sortable" class:sorted-asc={sortField === 'yearly_value' && sortDirection === 'asc'} class:sorted-desc={sortField === 'yearly_value' && sortDirection === 'desc'} onclick={() => toggleSort('yearly_value')}>
								Yearly Value
							</th>
							<th class="tal sortable" class:sorted-asc={sortField === 'disabled' && sortDirection === 'asc'} class:sorted-desc={sortField === 'disabled' && sortDirection === 'desc'} onclick={() => toggleSort('disabled')}>
								Disabled
							</th>
							<th class="tar">Actions</th>
						</tr>
							</thead>

							<tbody>
						{#each filteredAssets as a (a.id)}
							<tr class="asset-row" onclick={() => window.location.href = `/assets/${a.id}`}>
								<td class="tal">{a.tag || '-'}</td>
								<td class="tal">{a.name}</td>
								<td class="tal">{a.description}</td>
									<td class="tal">{(a.yearly_value || 0).toLocaleString()}</td>
								<td class="tal">{a.disabled ? 'Yes' : 'No'}</td>

								<td class="tar">
									<button
										class="button button_small"
										onclick={(e) => {
											e.stopPropagation();
											window.location.href = `/assets/${a.id}/edit`;
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

<!-- ADD MODAL -->
{#if showAddModal}
	<div class="modal-overlay" onclick={closeAddModal}>
		<div class="modal-content" role="dialog" aria-labelledby="add-modal-title" onclick={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2 id="add-modal-title" class="heading heading_2">Add Asset</h2>
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
							bind:value={newAsset.name}
							class="input__text"
							class:input__text_changed={newAsset.name && newAsset.name.length > 0}
							placeholder=""
							required
						/>
						<label for="add-name" class="input__label">Name</label>
					</div>

					<div class="input">
						<input
							id="add-description"
							type="text"
							bind:value={newAsset.description}
							class="input__text"
							class:input__text_changed={newAsset.description && newAsset.description.length > 0}
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
							Create
						</button>
					</div>
				</form>
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

	:global(.asset-row) {
		transition: background-color 0.2s ease;
	}

	:global(.asset-row:hover) {
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
