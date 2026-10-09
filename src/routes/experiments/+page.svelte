<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Experiment } from '$lib/types/models';
	import { armLabel } from '$lib/experiments';
	import { formatDate } from '$lib/formatDate';
	import { API_BASE } from '$lib/config';
	import ExperimentQuickAdd from '$lib/ExperimentQuickAdd.svelte';

	type SortField = 'name' | 'arm' | 'email_header_status' | 'created_at';

	let experiments: Experiment[] = [];
	let loading = true;
	let error: string | null = null;
	let filteredExperiments: Experiment[] = [];
	let showAddModal = false;

	let sortField: SortField | null = 'name';
	let sortDirection: 'asc' | 'desc' = 'asc';

	const apiBase = API_BASE;

	$: filteredExperiments = filterExperiments(experiments, $globalSearch, sortField, sortDirection);

	onMount(loadExperiments);

	async function loadExperiments() {
		try {
			loading = true;
			error = null;
			const response = await fetch(`${apiBase}/experiments`);
			if (!response.ok) throw new Error('Failed to fetch experiments');
			experiments = await response.json();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	}

	function filterExperiments(
		items: Experiment[],
		search: string,
		field: SortField | null,
		dir: 'asc' | 'desc'
	): Experiment[] {
		let result = items;
		if (search.trim() !== '') {
			const term = search.toLowerCase();
			result = result.filter(
				(e) =>
					(e.name || '').toLowerCase().includes(term) ||
					(e.description || '').toLowerCase().includes(term) ||
					(e.arm || '').toLowerCase().includes(term)
			);
		}
		if (field) {
			result = [...result].sort((a, b) => {
				const comparison = String(a[field] ?? '').localeCompare(String(b[field] ?? ''));
				return dir === 'asc' ? comparison : -comparison;
			});
		}
		return result;
	}

	function toggleSort(field: SortField) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}

	function handleCreated(experiment: Experiment) {
		showAddModal = false;
		window.location.href = `/experiments/${experiment.id}`;
	}

	async function handleDelete(experimentId: number) {
		if (!confirm('Are you sure you want to delete this experiment?')) return;
		try {
			const response = await fetch(`${apiBase}/experiments/${experimentId}`, { method: 'DELETE' });
			if (!response.ok) throw new Error('Failed to delete experiment');
			experiments = experiments.filter((e) => e.id !== experimentId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete experiment';
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Experiment
		</button>
		<h1 class="heading heading_1">Experiments</h1>
	</div>

	<div class="grid-row">
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">Outreach experiments</div>
				</div>

				{#if loading}
					<div class="message">Loading experiments...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredExperiments.length === 0}
					<div class="message">No experiments found</div>
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal sortable" class:sorted-asc={sortField === 'name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'name' && sortDirection === 'desc'} onclick={() => toggleSort('name')}>Name</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'arm' && sortDirection === 'asc'} class:sorted-desc={sortField === 'arm' && sortDirection === 'desc'} onclick={() => toggleSort('arm')}>Arm</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'email_header_status' && sortDirection === 'asc'} class:sorted-desc={sortField === 'email_header_status' && sortDirection === 'desc'} onclick={() => toggleSort('email_header_status')}>Email Header</th>
									<th class="tal">Steps</th>
									<th class="tal">Products</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'created_at' && sortDirection === 'asc'} class:sorted-desc={sortField === 'created_at' && sortDirection === 'desc'} onclick={() => toggleSort('created_at')}>Created</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>
							<tbody>
								{#each filteredExperiments as experiment (experiment.id)}
									<tr class="entity-row" onclick={() => (window.location.href = `/experiments/${experiment.id}`)}>
										<td class="tal">{experiment.name}</td>
										<td class="tal">{armLabel(experiment.arm)}</td>
										<td class="tal">{experiment.email_header_status}</td>
										<td class="tal">{experiment.steps?.length ?? 0}</td>
										<td class="tal">{experiment.product_ids?.length ?? 0}</td>
										<td class="tal">{formatDate(experiment.created_at) || '-'}</td>
										<td class="tar">
											<button class="button button_small" onclick={(e) => { e.stopPropagation(); window.location.href = `/experiments/${experiment.id}/edit`; }} title="Edit">✎</button>
											<button class="button button_small" onclick={(e) => { e.stopPropagation(); handleDelete(experiment.id); }} title="Delete">🗑</button>
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

<ExperimentQuickAdd open={showAddModal} onClose={() => (showAddModal = false)} onCreated={handleCreated} />
