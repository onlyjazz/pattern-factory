<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Path } from '$lib/db';

	let paths: Path[] = [];
	let loading = true;
	let error: string | null = null;

	let filteredPaths: Path[] = [];
	let showAddModal = false;
	let showEditModal = false;
	let pathToEdit = {} as Path;
	let newPath: Partial<Path> = { name: '' };

	let sortField: keyof Path | null = null;
	let sortDirection: 'asc' | 'desc' = 'asc';

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const response = await fetch(`${apiBase}/paths`);
			if (!response.ok) throw new Error('Failed to fetch paths');
			paths = await response.json();
			filterPaths();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function filterPaths() {
		filteredPaths = paths.filter((p) => {
			const matchesSearch =
				p.name.toLowerCase().includes($globalSearch.toLowerCase()) ||
				p.description?.toLowerCase().includes($globalSearch.toLowerCase());
			return matchesSearch;
		});
		sortPaths();
	}

	function sortPaths() {
		if (!sortField) return;
		filteredPaths = [...filteredPaths].sort((a, b) => {
			const aVal = a[sortField] || '';
			const bVal = b[sortField] || '';
			// For numeric fields like node count, use numeric comparison
			if (sortField === 'name') {
				const comparison = String(aVal).localeCompare(String(bVal));
				return sortDirection === 'asc' ? comparison : -comparison;
			} else {
				const comparison = String(aVal).localeCompare(String(bVal));
				return sortDirection === 'asc' ? comparison : -comparison;
			}
		});
	}

	function toggleSort(field: keyof Path) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
		sortPaths();
	}

	$: if (paths) filterPaths();
	$: if ($globalSearch !== undefined) filterPaths();

	function handleEdit(path: Path) {
		pathToEdit = { ...path };
		showEditModal = true;
	}

	function closeEditModal() {
		showEditModal = false;
		pathToEdit = {};
	}

	function closeAddModal() {
		showAddModal = false;
		newPath = { name: '' };
	}

	async function handleCreate() {
		try {
			if (!newPath.name || !newPath.name.trim()) {
				error = 'Path name is required';
				return;
			}

				const response = await fetch(`${apiBase}/paths`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						name: newPath.name,
						nodes: [],
						edges: []
					})
				});

			if (!response.ok) throw new Error('Failed to create path');
			const created = await response.json();
			paths = [...paths, created];
			filterPaths();
			closeAddModal();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create path';
		}
	}

	async function handleSave(updatedPath: Partial<Path>) {
		try {
			if (!updatedPath.name || !updatedPath.name.trim()) {
				error = 'Path name is required';
				return;
			}

			const response = await fetch(`${apiBase}/paths/${updatedPath.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: updatedPath.name
				})
			});

			if (!response.ok) throw new Error('Failed to update path');
			const updated = await response.json();
			paths = paths.map((p) => (p.id === updated.id ? updated : p));
			filterPaths();
			closeEditModal();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save path';
		}
	}

	async function handleDelete(pathId: string) {
		if (!confirm('Are you sure you want to delete this path?')) return;

		try {
			const response = await fetch(`${apiBase}/paths/${pathId}`, {
				method: 'DELETE'
			});

			if (!response.ok) throw new Error('Failed to delete path');
			paths = paths.filter((p) => p.id !== pathId);
			filterPaths();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete path';
		}
	}
</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Path
		</button>
		<h1 class="heading heading_1">Paths</h1>
	</div>

	<div class="grid-row">
		<!-- FULL WIDTH TABLE -->
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">Path Library</div>
				</div>

				{#if loading}
					<div class="message">Loading paths...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredPaths.length === 0}
					<div class="message">No paths found</div>
				{:else}
					<div class="table">
						<table>
							<thead>
									<tr>
										<th class="tal sortable" class:sorted-asc={sortField === 'name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name' && sortDirection === 'desc'} onclick={() => toggleSort('name')}>
											Name
										</th>
										<th class="tar">Actions</th>
									</tr>
							</thead>

							<tbody>
									{#each filteredPaths as p (p.id)}
										<tr>
											<td class="tal">{p.name}</td>

											<td class="tar">
												<a href="/paths/{p.id}" class="button button_small" title="Edit">
													✎
												</a>
												<button
													class="button button_small"
													onclick={() => handleDelete(p.id)}
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
</div>
<!-- end application-content-area -->

<!-- EDIT MODAL -->
{#if showEditModal && Object.keys(pathToEdit).length > 0}
	<div class="modal-overlay" onclick={closeEditModal}>
		<div
			class="modal-content"
			role="dialog"
			aria-labelledby="edit-modal-title"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="modal-header">
				<h2 id="edit-modal-title" class="heading heading_2">Edit Path</h2>
				<button class="modal-close" onclick={closeEditModal} title="Close">
					×
				</button>
			</div>

			<div class="modal-body">
				<form
					onsubmit={(e) => {
						e.preventDefault();
						handleSave(pathToEdit);
					}}
				>
						<div class="input">
							<input
								id="edit-name"
								type="text"
								bind:value={pathToEdit.name}
								class="input__text"
								class:input__text_changed={pathToEdit.name?.length > 0}
								required
							/>
							<label for="edit-name" class="input__label">Name</label>
						</div>

					<div class="modal-footer">
						<button
							type="button"
							class="button button_secondary"
							onclick={closeEditModal}
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

<!-- ADD MODAL -->
{#if showAddModal}
	<div class="modal-overlay" onclick={closeAddModal}>
		<div
			class="modal-content"
			role="dialog"
			aria-labelledby="add-modal-title"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="modal-header">
				<h2 id="add-modal-title" class="heading heading_2">Add Path</h2>
				<button class="modal-close" onclick={closeAddModal} title="Close">
					×
				</button>
			</div>

			<div class="modal-body">
				<form
					onsubmit={(e) => {
						e.preventDefault();
						handleCreate();
					}}
				>
						<div class="input">
							<input
								id="add-name"
								type="text"
								bind:value={newPath.name}
								class="input__text"
								class:input__text_changed={newPath.name?.length > 0}
								placeholder=""
								required
							/>
							<label for="add-name" class="input__label">Name</label>
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
	:global(td.tar button) {
		background: none !important;
		border: none !important;
	}

	:global(td.tar a) {
		background: none !important;
		border: none !important;
		text-decoration: none;
	}

	:global(td.tar) {
		vertical-align: top;
		white-space: nowrap;
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
