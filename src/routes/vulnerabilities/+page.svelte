<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import { modeStore } from '$lib/modeStore';
	import type { Vulnerability } from '$lib/db';
	
	let vulnerabilities: Vulnerability[] = [];
	let loading = true;
	let error: string | null = null;
	let addModalError: string | null = null;
	
	let filteredVulnerabilities: Vulnerability[] = [];
	let showAddModal = false;
	let activeModelId: number | null = null;
	let newVulnerability: Partial<Vulnerability> = {
		name: '', 
		description: '',
		disabled: false,
		model_id: 1
	};
	
	let sortField: keyof Vulnerability | string | null = 'name';
	let sortDirection: 'asc' | 'desc' = 'asc';
	
	const apiBase = 'http://localhost:8000';
	
	onMount(async () => {
		const unsubscribe = modeStore.subscribe((state) => {
			activeModelId = state.activeModel;
		});
		
		try {
			const response = await fetch(`${apiBase}/vulnerabilities`);
			if (!response.ok) throw new Error('Failed to fetch vulnerabilities');
			const data = await response.json();
			vulnerabilities = data.map((v: any) => ({ ...v, id: String(v.id) }));
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
		
		return unsubscribe;
	});
	
	function filterAndSortVulnerabilities(items: Vulnerability[], search: string, field: keyof Vulnerability | string | null, direction: 'asc' | 'desc'): Vulnerability[] {
		let result = items;
		
		// Apply search filter
		if (search.trim() !== '') {
			const term = search.toLowerCase();
			result = result.filter(v => {
				const name = (v.name || '').toLowerCase();
				const description = (v.description || '').toLowerCase();
				return name.includes(term) || description.includes(term);
			});
		}
		
		// Apply sorting
		if (field) {
			result = [...result].sort((a, b) => {
				const aVal = a[field as keyof Vulnerability] || '';
				const bVal = b[field as keyof Vulnerability] || '';
				const comparison = String(aVal).localeCompare(String(bVal));
				return direction === 'asc' ? comparison : -comparison;
			});
		}
		
		return result;
	}
	
	function toggleSort(field: keyof Vulnerability) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}
	
	$: filteredVulnerabilities = filterAndSortVulnerabilities(vulnerabilities, $globalSearch, sortField, sortDirection);
	
	function closeAddModal() {
		showAddModal = false;
		newVulnerability = { 
			name: '', 
			description: '',
			disabled: false,
			model_id: 1
		};
		addModalError = null;
	}
	
	async function handleCreate() {
		try {
			addModalError = null;
			if (!newVulnerability.name || !newVulnerability.description) {
				addModalError = 'Please fill in all required fields';
				return;
			}
		const response = await fetch(`${apiBase}/vulnerabilities`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				name: newVulnerability.name,
				description: newVulnerability.description,
				disabled: newVulnerability.disabled || false,
				model_id: activeModelId || 1,
			})
		});
			if (!response.ok) throw new Error('Failed to create vulnerability');
			const created = await response.json();
			vulnerabilities = [...vulnerabilities, { ...created, id: String(created.id) }];
			closeAddModal();
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create vulnerability';
		}
	}
	
	async function handleDelete(vulnerabilityId: string) {
		if (!confirm('Are you sure you want to delete this vulnerability?')) return;
		
		try {
			const response = await fetch(`${apiBase}/vulnerabilities/${vulnerabilityId}`, {
				method: 'DELETE'
			});
			
			if (!response.ok) throw new Error('Failed to delete vulnerability');
			vulnerabilities = vulnerabilities.filter(v => v.id !== vulnerabilityId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete vulnerability';
		}
	}

</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Vulnerability
		</button>
		<h1 class="heading heading_1">Vulnerabilities</h1>
	</div>

	<div class="grid-row">
		<!-- FULL WIDTH TABLE -->
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">Vulnerability Library</div>
				</div>

				{#if loading}
					<div class="message">Loading vulnerabilities...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredVulnerabilities.length === 0}
					<div class="message">No vulnerabilities found</div>
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
									<th class="tal sortable" class:sorted-asc={sortField === 'disabled' && sortDirection === 'asc'} class:sorted-desc={sortField === 'disabled' && sortDirection === 'desc'} onclick={() => toggleSort('disabled')}>
										Disabled
									</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>

							<tbody>
								{#each filteredVulnerabilities as v (v.id)}
									<tr class="vulnerability-row" onclick={() => window.location.href = `/vulnerabilities/${v.id}`}>
										<td class="tal">V{v.id}</td>
										<td class="tal">{v.name}</td>
										<td class="tal">{v.description}</td>
										<td class="tal">{v.disabled ? 'Yes' : 'No'}</td>

										<td class="tar">
											<button
												class="button button_small"
												onclick={(e) => {
													e.stopPropagation();
													window.location.href = `/vulnerabilities/${v.id}/edit`;
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
				<h2 id="add-modal-title" class="heading heading_2">Add Vulnerability</h2>
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
							bind:value={newVulnerability.name}
							class="input__text"
							class:input__text_changed={newVulnerability.name && newVulnerability.name.length > 0}
							placeholder=""
							required
						/>
						<label for="add-name" class="input__label">Name</label>
					</div>

					<div class="input">
						<input
							id="add-description"
							type="text"
							bind:value={newVulnerability.description}
							class="input__text"
							class:input__text_changed={newVulnerability.description && newVulnerability.description.length > 0}
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

	:global(.vulnerability-row) {
		transition: background-color 0.2s ease;
	}

	:global(.vulnerability-row:hover) {
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
