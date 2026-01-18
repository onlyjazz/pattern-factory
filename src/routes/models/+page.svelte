<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import { modeStore } from '$lib/modeStore';
	import type { Model } from '$lib/db';
	
	let models: Model[] = [];
	let loading = true;
	let error: string | null = null;
	let addModalError: string | null = null;
	
	let filteredModels: Model[] = [];
	let showAddModal = false;
	let newModel: Partial<Model> = { 
		name: '', 
		version: '',
		author: '',
		company: '',
		category: '',
		keywords: '',
		description: ''
	};
	
	let sortField: keyof Model | null = null;
	let sortDirection: 'asc' | 'desc' = 'asc';
	
	const apiBase = 'http://localhost:8000';
	
	onMount(async () => {
		try {
			const response = await fetch(`${apiBase}/models`);
			if (!response.ok) throw new Error('Failed to fetch models');
			const data = await response.json();
			models = data.map((m: any) => ({ ...m, id: m.id }));
			filterModels();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});
	
	function filterModels() {
		filteredModels = models.filter(m => {
			const matchesSearch = m.name.toLowerCase().includes($globalSearch.toLowerCase()) ||
				(m.description?.toLowerCase().includes($globalSearch.toLowerCase())) ||
				(m.author?.toLowerCase().includes($globalSearch.toLowerCase())) ||
				(m.company?.toLowerCase().includes($globalSearch.toLowerCase()));
			return matchesSearch;
		});
		sortModels();
	}
	
	function sortModels() {
		if (!sortField) return;
		filteredModels = [...filteredModels].sort((a, b) => {
			const aVal = a[sortField] || '';
			const bVal = b[sortField] || '';
			const comparison = String(aVal).localeCompare(String(bVal));
			return sortDirection === 'asc' ? comparison : -comparison;
		});
	}
	
	function toggleSort(field: keyof Model) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
		sortModels();
	}
	
	$: if (models) filterModels();
	$: if ($globalSearch !== undefined) filterModels();
	
	function closeAddModal() {
		showAddModal = false;
		newModel = { 
			name: '', 
			version: '',
			author: '',
			company: '',
			category: '',
			keywords: '',
			description: ''
		};
		addModalError = null;
	}
	
	async function handleCreate() {
		try {
			addModalError = null;
			if (!newModel.name) {
				addModalError = 'Model name is required';
				return;
			}
			const response = await fetch(`${apiBase}/models`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: newModel.name,
					version: newModel.version || null,
					author: newModel.author || null,
					company: newModel.company || null,
					category: newModel.category || null,
					keywords: newModel.keywords || null,
					description: newModel.description || null
				})
			});
			if (!response.ok) throw new Error('Failed to create model');
			const created = await response.json();
			models = [...models, created];
			filterModels();
			closeAddModal();
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create model';
		}
	}
	
	async function handleActivate(modelId: number) {
		try {
			error = null;
			const response = await fetch(`${apiBase}/models/${modelId}/activate`, {
				method: 'POST'
			});
			if (!response.ok) throw new Error('Failed to activate model');
			// Update mode store to reflect active model
			modeStore.setActiveModel(modelId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to activate model';
		}
	}
	
	async function handleDelete(modelId: number) {
		if (!confirm('Are you sure you want to delete this model? All associated data will be deleted.')) return;
		
		try {
			const response = await fetch(`${apiBase}/models/${modelId}`, {
				method: 'DELETE'
			});
			
			if (!response.ok) throw new Error('Failed to delete model');
			models = models.filter(m => m.id !== modelId);
			filterModels();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete model';
		}
	}

</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Model
		</button>
		<h1 class="heading heading_1">Models</h1>
	</div>

	{#if error}
		<div class="message message-error" style="margin: 1rem 0;">Error: {error}</div>
	{/if}

	<div class="grid-row">
		<!-- FULL WIDTH TABLE -->
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">Model Library</div>
				</div>

				{#if loading}
					<div class="message">Loading models...</div>
				{:else if error && filteredModels.length === 0}
					<div class="message">Failed to load models</div>
				{:else if filteredModels.length === 0}
					<div class="message">No models found</div>
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal sortable" class:sorted-asc={sortField === 'name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name' && sortDirection === 'desc'} onclick={() => toggleSort('name')}>
										Name
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'version' && sortDirection === 'asc'} class:sorted-desc={sortField === 'version' && sortDirection === 'desc'} onclick={() => toggleSort('version')}>
										Version
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'author' && sortDirection === 'asc'} class:sorted-desc={sortField === 'author' && sortDirection === 'desc'} onclick={() => toggleSort('author')}>
										Author
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'company' && sortDirection === 'asc'} class:sorted-desc={sortField === 'company' && sortDirection === 'desc'} onclick={() => toggleSort('company')}>
										Company
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'description' && sortDirection === 'asc'} class:sorted-desc={sortField === 'description' && sortDirection === 'desc'} onclick={() => toggleSort('description')}>
										Description
									</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>

							<tbody>
								{#each filteredModels as m (m.id)}
									<tr class="model-row clickable" class:active-model={$modeStore.activeModel === m.id} onclick={() => handleActivate(m.id)}>
										<td class="tal"><strong>{m.name}</strong> {#if $modeStore.activeModel === m.id}<span class="active-badge">✓ Active</span>{/if}</td>
										<td class="tal">{m.version || '-'}</td>
										<td class="tal">{m.author || '-'}</td>
										<td class="tal">{m.company || '-'}</td>
										<td class="tal">{m.description || '-'}</td>

										<td class="tar" onclick={(e) => e.stopPropagation()}>
											<a href="/models/{m.id}/edit" class="button button_small" title="Edit">✎</a>
											<button class="button button_small" onclick={() => handleDelete(m.id)} title="Delete">🗑</button>
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
				<h2 id="add-modal-title" class="heading heading_2">Add Model</h2>
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
							bind:value={newModel.name}
							class="input__text"
							class:input__text_changed={newModel.name && newModel.name.length > 0}
							placeholder=""
							required
						/>
						<label for="add-name" class="input__label">Name *</label>
					</div>

					<div class="input">
						<input
							id="add-version"
							type="text"
							bind:value={newModel.version}
							class="input__text"
							class:input__text_changed={newModel.version && newModel.version.length > 0}
						/>
						<label for="add-version" class="input__label">Version</label>
					</div>

					<div class="input">
						<input
							id="add-author"
							type="text"
							bind:value={newModel.author}
							class="input__text"
							class:input__text_changed={newModel.author && newModel.author.length > 0}
						/>
						<label for="add-author" class="input__label">Author</label>
					</div>

					<div class="input">
						<input
							id="add-company"
							type="text"
							bind:value={newModel.company}
							class="input__text"
							class:input__text_changed={newModel.company && newModel.company.length > 0}
						/>
						<label for="add-company" class="input__label">Company</label>
					</div>

					<div class="input">
						<input
							id="add-category"
							type="text"
							bind:value={newModel.category}
							class="input__text"
							class:input__text_changed={newModel.category && newModel.category.length > 0}
						/>
						<label for="add-category" class="input__label">Category</label>
					</div>

					<div class="input">
						<input
							id="add-keywords"
							type="text"
							bind:value={newModel.keywords}
							class="input__text"
							class:input__text_changed={newModel.keywords && newModel.keywords.length > 0}
						/>
						<label for="add-keywords" class="input__label">Keywords</label>
					</div>

					<div class="input">
						<textarea
							id="add-description"
							bind:value={newModel.description}
							class="input__text"
							class:input__text_changed={newModel.description && newModel.description.length > 0}
							rows="4"
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

	:global(.model-row) {
		transition: background-color 0.2s ease;
	}

	:global(.model-row.clickable) {
		cursor: pointer;
	}

	:global(.model-row.clickable:hover) {
		background-color: #f5f5f5;
	}

	:global(.model-row.active-model) {
		background-color: #e8f5e9;
		font-weight: 500;
	}

	:global(.model-row.active-model:hover) {
		background-color: #c8e6c9;
	}

	:global(.active-badge) {
		display: inline-block;
		margin-left: 0.5rem;
		padding: 0.2rem 0.5rem;
		background-color: #4caf50;
		color: white;
		border-radius: 3px;
		font-size: 0.75rem;
		font-weight: 600;
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

	:global(.input__text) {
		width: 100%;
	}

	textarea.input__text {
		font-family: inherit;
		resize: vertical;
	}
</style>
