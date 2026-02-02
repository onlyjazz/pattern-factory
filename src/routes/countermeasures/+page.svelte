<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Countermeasure } from '$lib/db';
	
	let countermeasures: Countermeasure[] = [];
	let loading = true;
	let error: string | null = null;
	let addModalError: string | null = null;
	
	let filteredCountermeasures: Countermeasure[] = [];
	let showAddModal = false;
	let newCountermeasure: Partial<Countermeasure> = { 
		name: '', 
		description: '',
		fixed_implementation_cost: 0,
		fixed_cost_period: 12,
		recurring_implementation_cost: 0,
		include_fixed_cost: true,
		include_recurring_cost: true,
		implemented: false,
		disabled: false,
		model_id: 1
	};
	
let sortField: keyof Countermeasure | string | null = 'tag';
	let sortDirection: 'asc' | 'desc' = 'asc';
	
	const apiBase = 'http://localhost:8000';
	
	onMount(async () => {
		try {
			const response = await fetch(`${apiBase}/countermeasures`);
			if (!response.ok) throw new Error('Failed to fetch countermeasures');
			const data = await response.json();
			countermeasures = data.map((c: any) => ({ ...c, id: String(c.id) }));
			filterCountermeasures();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});
	
	function filterCountermeasures() {
		filteredCountermeasures = countermeasures.filter(c => {
			const matchesSearch = c.name.toLowerCase().includes($globalSearch.toLowerCase()) ||
				c.description.toLowerCase().includes($globalSearch.toLowerCase());
			return matchesSearch;
		});
		sortCountermeasures();
	}
	
	function sortCountermeasures() {
		if (!sortField) return;
		filteredCountermeasures = [...filteredCountermeasures].sort((a, b) => {
			let aVal = a[sortField] || '';
			let bVal = b[sortField] || '';
			
			// For 'tag' field, sort by numeric id
			if (sortField === 'tag') {
				const aNum = parseInt(String(a.id), 10);
				const bNum = parseInt(String(b.id), 10);
				const comparison = aNum - bNum;
				return sortDirection === 'asc' ? comparison : -comparison;
			}
			
			const comparison = String(aVal).localeCompare(String(bVal));
			return sortDirection === 'asc' ? comparison : -comparison;
		});
	}
	
	function toggleSort(field: keyof Countermeasure) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
		sortCountermeasures();
	}
	
	$: if (countermeasures) filterCountermeasures();
	$: if ($globalSearch !== undefined) filterCountermeasures();
	
	function closeAddModal() {
		showAddModal = false;
		newCountermeasure = { 
			name: '', 
			description: '',
			fixed_implementation_cost: 0,
			fixed_cost_period: 12,
			recurring_implementation_cost: 0,
			include_fixed_cost: true,
			include_recurring_cost: true,
			implemented: false,
			disabled: false,
			model_id: 1
		};
		addModalError = null;
	}
	
	async function handleCreate() {
		try {
			addModalError = null;
			if (!newCountermeasure.name || !newCountermeasure.description) {
				addModalError = 'Please fill in all required fields';
				return;
			}
			const response = await fetch(`${apiBase}/countermeasures`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: newCountermeasure.name,
					description: newCountermeasure.description,
					fixed_implementation_cost: newCountermeasure.fixed_implementation_cost || 0,
					fixed_cost_period: newCountermeasure.fixed_cost_period || 12,
					recurring_implementation_cost: newCountermeasure.recurring_implementation_cost || 0,
					include_fixed_cost: newCountermeasure.include_fixed_cost !== undefined ? newCountermeasure.include_fixed_cost : true,
					include_recurring_cost: newCountermeasure.include_recurring_cost !== undefined ? newCountermeasure.include_recurring_cost : true,
					implemented: newCountermeasure.implemented || false,
					disabled: newCountermeasure.disabled || false,
					model_id: newCountermeasure.model_id || 1,
				})
			});
			if (!response.ok) throw new Error('Failed to create countermeasure');
			const created = await response.json();
			countermeasures = [...countermeasures, { ...created, id: String(created.id) }];
			filterCountermeasures();
			closeAddModal();
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create countermeasure';
		}
	}
	
	async function handleDelete(countermeasureId: string) {
		if (!confirm('Are you sure you want to delete this countermeasure?')) return;
		
		try {
			const response = await fetch(`${apiBase}/countermeasures/${countermeasureId}`, {
				method: 'DELETE'
			});
			
			if (!response.ok) throw new Error('Failed to delete countermeasure');
			countermeasures = countermeasures.filter(c => c.id !== countermeasureId);
			filterCountermeasures();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete countermeasure';
		}
	}

</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Countermeasure
		</button>
		<h1 class="heading heading_1">Countermeasures</h1>
	</div>

	<div class="grid-row">
		<!-- FULL WIDTH TABLE -->
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">Countermeasure Library</div>
				</div>

				{#if loading}
					<div class="message">Loading countermeasures...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredCountermeasures.length === 0}
					<div class="message">No countermeasures found</div>
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
									<th class="tal sortable" class:sorted-asc={sortField === 'yearly_cost' && sortDirection === 'asc'} class:sorted-desc={sortField === 'yearly_cost' && sortDirection === 'desc'} onclick={() => toggleSort('yearly_cost')}>
										Yearly Cost
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'implemented' && sortDirection === 'asc'} class:sorted-desc={sortField === 'implemented' && sortDirection === 'desc'} onclick={() => toggleSort('implemented')}>
										Implemented
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'disabled' && sortDirection === 'asc'} class:sorted-desc={sortField === 'disabled' && sortDirection === 'desc'} onclick={() => toggleSort('disabled')}>
										Disabled
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'version' && sortDirection === 'asc'} class:sorted-desc={sortField === 'version' && sortDirection === 'desc'} onclick={() => toggleSort('version')}>
										Version
									</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>

							<tbody>
								{#each filteredCountermeasures as c (c.id)}
									<tr class="countermeasure-row">
										<td class="tal">C{c.id}</td>
										<td class="tal">{c.name}</td>
										<td class="tal">{c.description}</td>
										<td class="tal">${c.yearly_cost || 0}</td>
										<td class="tal">{c.implemented ? 'Yes' : 'No'}</td>
										<td class="tal">{c.disabled ? 'Yes' : 'No'}</td>
										<td class="tal">{c.version || 1}</td>

										<td class="tar">
											<a href="/countermeasures/{c.id}" class="button button_small" title="Edit">✎</a>
											<button class="button button_small" onclick={() => handleDelete(c.id)} title="Delete">🗑</button>
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
				<h2 id="add-modal-title" class="heading heading_2">Add Countermeasure</h2>
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
							bind:value={newCountermeasure.name}
							class="input__text"
							class:input__text_changed={newCountermeasure.name && newCountermeasure.name.length > 0}
							placeholder=""
							required
						/>
						<label for="add-name" class="input__label">Name</label>
					</div>

					<div class="input">
						<input
							id="add-description"
							type="text"
							bind:value={newCountermeasure.description}
							class="input__text"
							class:input__text_changed={newCountermeasure.description && newCountermeasure.description.length > 0}
							placeholder=""
							required
						/>
						<label for="add-description" class="input__label">Description</label>
					</div>

					<div class="input">
						<input
							id="add-fixed-cost"
							type="number"
							bind:value={newCountermeasure.fixed_implementation_cost}
							class="input__text"
						/>
						<label for="add-fixed-cost" class="input__label">Fixed Implementation Cost</label>
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

	:global(.countermeasure-row) {
		transition: background-color 0.2s ease;
	}

	:global(.countermeasure-row:hover) {
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
