<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Person, Organization } from '$lib/db';
	import { API_BASE } from '$lib/config';

	let people: Person[] = [];
	let orgs: Organization[] = [];
	let loading = true;
	let error: string | null = null;
	let filteredPeople: Person[] = [];

	let showAddModal = false;
	let addModalError: string | null = null;
	let newPerson = { name: '', job_description: '', org_id: null as number | null };

	let sortField: keyof Person | null = 'name';
	let sortDirection: 'asc' | 'desc' = 'asc';

	const apiBase = API_BASE;

	$: filteredPeople = filterPeople(people, $globalSearch, sortField, sortDirection);

	onMount(async () => {
		try {
			const [peopleRes, orgsRes] = await Promise.all([
				fetch(`${apiBase}/people`),
				fetch(`${apiBase}/orgs`)
			]);
			if (!peopleRes.ok) throw new Error('Failed to fetch people');
			const data = await peopleRes.json();
			people = data.map((p: any) => ({ ...p, id: String(p.id) }));
			if (orgsRes.ok) orgs = await orgsRes.json();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function orgName(orgId?: number | null): string {
		const match = orgs.find(o => Number(o.id) === orgId);
		return match ? match.name : '-';
	}

	function filterPeople(items: Person[], search: string, field: keyof Person | null, dir: 'asc' | 'desc'): Person[] {
		let result = items;
		if (search.trim() !== '') {
			const term = search.toLowerCase();
			result = result.filter(p =>
				(p.name || '').toLowerCase().includes(term) ||
				(p.job_description || '').toLowerCase().includes(term) ||
				(p.email || '').toLowerCase().includes(term)
			);
		}
		if (field) {
			result = [...result].sort((a, b) => {
				const av = a[field] || '';
				const bv = b[field] || '';
				const comparison = String(av).localeCompare(String(bv));
				return dir === 'asc' ? comparison : -comparison;
			});
		}
		return result;
	}

	function toggleSort(field: keyof Person) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}

	function closeAddModal() {
		showAddModal = false;
		newPerson = { name: '', job_description: '', org_id: null };
		addModalError = null;
	}

	async function handleCreate() {
		try {
			addModalError = null;
			if (!newPerson.name) {
				addModalError = 'Name is required';
				return;
			}
			const response = await fetch(`${apiBase}/people`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: newPerson.name,
					job_description: newPerson.job_description || null,
					org_id: newPerson.org_id
				})
			});
			if (!response.ok) throw new Error('Failed to create person');
			const created = await response.json();
			closeAddModal();
			window.location.href = `/people/${created.id}`;
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create person';
		}
	}

	async function handleDelete(personId: string) {
		if (!confirm('Are you sure you want to delete this person?')) return;
		try {
			const response = await fetch(`${apiBase}/people/${personId}`, { method: 'DELETE' });
			if (!response.ok) throw new Error('Failed to delete person');
			people = people.filter(p => p.id !== personId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete person';
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Person
		</button>
		<h1 class="heading heading_1">People</h1>
	</div>

	<div class="grid-row">
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">People</div>
				</div>

				{#if loading}
					<div class="message">Loading people...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredPeople.length === 0}
					<div class="message">No people found</div>
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal sortable" class:sorted-asc={sortField === 'name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name' && sortDirection === 'desc'} onclick={() => toggleSort('name')}>Name</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'job_description' && sortDirection === 'asc'} class:sorted-desc={sortField === 'job_description' && sortDirection === 'desc'} onclick={() => toggleSort('job_description')}>Job Description</th>
									<th class="tal">Org</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'email' && sortDirection === 'asc'} class:sorted-desc={sortField === 'email' && sortDirection === 'desc'} onclick={() => toggleSort('email')}>Email</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>
							<tbody>
								{#each filteredPeople as p (p.id)}
									<tr class="entity-row" onclick={() => (window.location.href = `/people/${p.id}`)}>
										<td class="tal">{p.name}</td>
										<td class="tal">{p.job_description || '-'}</td>
										<td class="tal">{orgName(p.org_id)}</td>
										<td class="tal">{p.email || '-'}</td>
										<td class="tar">
											<button class="button button_small" onclick={(e) => { e.stopPropagation(); window.location.href = `/people/${p.id}/edit`; }} title="Edit">✎</button>
											<button class="button button_small" onclick={(e) => { e.stopPropagation(); handleDelete(p.id); }} title="Delete">🗑</button>
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
		<div class="modal-content" role="dialog" aria-labelledby="add-person-title" tabindex="0" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2 id="add-person-title" class="heading heading_2">Add Person</h2>
				<button type="button" class="modal-close" onclick={closeAddModal} title="Close">×</button>
			</div>
			<div class="modal-body">
				{#if addModalError}
					<div class="message message-error error-margin">Error: {addModalError}</div>
				{/if}
				<form onsubmit={(e) => { e.preventDefault(); handleCreate(); }}>
					<div class="input">
						<input id="add-person-name" type="text" bind:value={newPerson.name} class="input__text" class:input__text_changed={newPerson.name.length > 0} required />
						<label for="add-person-name" class="input__label">Name</label>
					</div>
					<div class="input">
						<input id="add-person-job" type="text" bind:value={newPerson.job_description} class="input__text" class:input__text_changed={newPerson.job_description.length > 0} />
						<label for="add-person-job" class="input__label">Job Description</label>
					</div>
					<div class="input input_select">
						<select id="add-person-org" bind:value={newPerson.org_id} class="input__text" class:input__text_changed={newPerson.org_id !== null}>
							<option value={null}>No organization</option>
							{#each orgs as o (o.id)}
								<option value={Number(o.id)}>{o.name}</option>
							{/each}
						</select>
						<label for="add-person-org" class="input__label">Organization</label>
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
