<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Organization, Status } from '$lib/db';
	import { API_BASE } from '$lib/config';

	let orgs: Organization[] = [];
	let statuses: Status[] = [];
	let loading = true;
	let error: string | null = null;
	let filteredOrgs: Organization[] = [];

	let showAddModal = false;
	let addModalError: string | null = null;
	let newOrg = { name: '', headquarters: '' };

	let sortField: keyof Organization | null = 'name';
	let sortDirection: 'asc' | 'desc' = 'asc';

	const apiBase = API_BASE;

	$: filteredOrgs = filterOrgs(orgs, $globalSearch, sortField, sortDirection);

	onMount(async () => {
		try {
			const [orgsRes, statusesRes] = await Promise.all([
				fetch(`${apiBase}/orgs`),
				fetch(`${apiBase}/statuses`)
			]);
			if (!orgsRes.ok) throw new Error('Failed to fetch organizations');
			const data = await orgsRes.json();
			orgs = data.map((o: any) => ({ ...o, id: String(o.id) }));
			if (statusesRes.ok) statuses = await statusesRes.json();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function statusName(statusId?: number | null): string {
		const match = statuses.find(s => s.id === statusId);
		return match ? match.name : '-';
	}

	function filterOrgs(items: Organization[], search: string, field: keyof Organization | null, dir: 'asc' | 'desc'): Organization[] {
		let result = items;
		if (search.trim() !== '') {
			const term = search.toLowerCase();
			result = result.filter(o =>
				(o.name || '').toLowerCase().includes(term) ||
				(o.name_before_acquisition || '').toLowerCase().includes(term) ||
				(o.headquarters || '').toLowerCase().includes(term) ||
				statusName(o.status_id).toLowerCase().includes(term)
			);
		}
		if (field) {
			result = [...result].sort((a, b) => {
				if (field === 'size' || field === 'tier') {
					const av = Number(a[field] || 0);
					const bv = Number(b[field] || 0);
					return dir === 'asc' ? av - bv : bv - av;
				}
				const av = a[field] || '';
				const bv = b[field] || '';
				const comparison = String(av).localeCompare(String(bv));
				return dir === 'asc' ? comparison : -comparison;
			});
		}
		return result;
	}

	function toggleSort(field: keyof Organization) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}

	function closeAddModal() {
		showAddModal = false;
		newOrg = { name: '', headquarters: '' };
		addModalError = null;
	}

	async function handleCreate() {
		try {
			addModalError = null;
			if (!newOrg.name) {
				addModalError = 'Name is required';
				return;
			}
			const response = await fetch(`${apiBase}/orgs`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: newOrg.name,
					headquarters: newOrg.headquarters || null
				})
			});
			if (!response.ok) throw new Error('Failed to create organization');
			const created = await response.json();
			closeAddModal();
			window.location.href = `/orgs/${created.id}`;
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create organization';
		}
	}

	async function handleDelete(orgId: string) {
		if (!confirm('Are you sure you want to delete this organization?')) return;
		try {
			const response = await fetch(`${apiBase}/orgs/${orgId}`, { method: 'DELETE' });
			if (!response.ok) throw new Error('Failed to delete organization');
			orgs = orgs.filter(o => o.id !== orgId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete organization';
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Org
		</button>
		<h1 class="heading heading_1">Orgs</h1>
	</div>

	<div class="grid-row">
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">Organizations</div>
				</div>

				{#if loading}
					<div class="message">Loading organizations...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredOrgs.length === 0}
					<div class="message">No organizations found</div>
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal sortable" class:sorted-asc={sortField === 'name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name' && sortDirection === 'desc'} onclick={() => toggleSort('name')}>Name</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'name_before_acquisition' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name_before_acquisition' && sortDirection === 'desc'} onclick={() => toggleSort('name_before_acquisition')}>Name Before Acquisition</th>
									<th class="tal">Status</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'tier' && sortDirection === 'asc'} class:sorted-desc={sortField === 'tier' && sortDirection === 'desc'} onclick={() => toggleSort('tier')}>Tier</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'size' && sortDirection === 'asc'} class:sorted-desc={sortField === 'size' && sortDirection === 'desc'} onclick={() => toggleSort('size')}>Size</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'headquarters' && sortDirection === 'asc'} class:sorted-desc={sortField === 'headquarters' && sortDirection === 'desc'} onclick={() => toggleSort('headquarters')}>Headquarters</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>
							<tbody>
								{#each filteredOrgs as o (o.id)}
									<tr class="entity-row" onclick={() => (window.location.href = `/orgs/${o.id}`)}>
										<td class="tal">{o.name}</td>
										<td class="tal">{o.name_before_acquisition || '-'}</td>
										<td class="tal">{statusName(o.status_id)}</td>
										<td class="tal">{o.tier ?? '-'}</td>
										<td class="tal">{(o.size || 0).toLocaleString()}</td>
										<td class="tal">{o.headquarters || '-'}</td>
										<td class="tar">
											<button class="button button_small" onclick={(e) => { e.stopPropagation(); window.location.href = `/orgs/${o.id}/edit`; }} title="Edit">✎</button>
											<button class="button button_small" onclick={(e) => { e.stopPropagation(); handleDelete(o.id); }} title="Delete">🗑</button>
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

{#if showAddModal}
	<div class="modal-overlay" role="presentation" onclick={closeAddModal} onkeydown={(e) => e.key === 'Escape' && closeAddModal()}>
		<div class="modal-content" role="dialog" aria-labelledby="add-org-title" tabindex="0" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2 id="add-org-title" class="heading heading_2">Add Org</h2>
				<button type="button" class="modal-close" onclick={closeAddModal} title="Close">×</button>
			</div>
			<div class="modal-body">
				{#if addModalError}
					<div class="message message-error error-margin">Error: {addModalError}</div>
				{/if}
				<form onsubmit={(e) => { e.preventDefault(); handleCreate(); }}>
					<div class="input">
						<input id="add-org-name" type="text" bind:value={newOrg.name} class="input__text" class:input__text_changed={newOrg.name.length > 0} required />
						<label for="add-org-name" class="input__label">Name</label>
					</div>
					<div class="input">
						<input id="add-org-hq" type="text" bind:value={newOrg.headquarters} class="input__text" class:input__text_changed={newOrg.headquarters.length > 0} />
						<label for="add-org-hq" class="input__label">Headquarters</label>
					</div>
					<div class="modal-footer">
						<button type="button" class="button button_secondary" onclick={closeAddModal}>Cancel</button>
						<button type="submit" class="button button_green">Save</button>
					</div>
				</form>
			</div>
		</div>
	</div>
{/if}
