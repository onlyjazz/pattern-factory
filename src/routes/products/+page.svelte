<script lang="ts">
	import { onMount } from 'svelte';
	import { LineChart } from 'lucide-svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Organization } from '$lib/db';
	import type { Experiment } from '$lib/types/models';
	import { matchesFilter, parseQuery, type Query } from '$lib/queryFilter';
	import { productQueryFields, type ProductRow } from '$lib/productQueryFields';
	import { formatDate } from '$lib/formatDate';
	import { API_BASE } from '$lib/config';

	let products: ProductRow[] = [];
	let orgs: Organization[] = [];
	let experiments: Experiment[] = [];
	let loading = true;
	let error: string | null = null;
	let filteredProducts: ProductRow[] = [];

	let selectedProductIds: string[] = [];

	let showAddModal = false;
	let addModalError: string | null = null;
	let newProduct = { submission_number: '', device: '', org_id: null as number | null };

	let sortField: keyof ProductRow | null = 'updated_at';
	let sortDirection: 'asc' | 'desc' = 'desc';

	const apiBase = API_BASE;

	$: productQuery = parseQuery($globalSearch, productQueryFields);
	$: filteredProducts = filterProducts(products, productQuery, sortField, sortDirection);
	$: allFilteredSelected =
		filteredProducts.length > 0 && filteredProducts.every((p) => selectedProductIds.includes(p.id));
	// Selections survive filter changes, so surface the ones the current filter
	// hides instead of quietly sending a different batch to Close.
	$: visibleSelectedCount = filteredProducts.filter((p) => selectedProductIds.includes(p.id)).length;
	$: hiddenSelectedCount = selectedProductIds.length - visibleSelectedCount;

	onMount(async () => {
		try {
			const [productsRes, orgsRes, experimentsRes] = await Promise.all([
				fetch(`${apiBase}/products`),
				fetch(`${apiBase}/orgs`),
				fetch(`${apiBase}/experiments`)
			]);
			if (!productsRes.ok) throw new Error('Failed to fetch products');
			if (orgsRes.ok) orgs = await orgsRes.json();
			if (experimentsRes.ok) experiments = await experimentsRes.json();
			const data = await productsRes.json();
			products = data.map((p: any): ProductRow => {
				const org = orgs.find((o) => Number(o.id) === p.org_id);
				return {
					...p,
					id: String(p.id),
					org_name: org?.name ?? null,
					arm: org?.arm ?? null,
					tier: org?.tier ?? null,
					size: org?.size ?? null
				};
			});
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function filterProducts(items: ProductRow[], query: Query<ProductRow>, field: keyof ProductRow | null, dir: 'asc' | 'desc'): ProductRow[] {
		let result = items;
		if (query.kind === 'text') {
			const term = query.term.toLowerCase().trim();
			if (term !== '') {
				result = result.filter(p =>
					(p.device || '').toLowerCase().includes(term) ||
					(p.submission_number || '').toLowerCase().includes(term) ||
					(p.panel || '').toLowerCase().includes(term) ||
					(p.tag || '').toLowerCase().includes(term) ||
					(p.org_name || '').toLowerCase().includes(term)
				);
			}
		} else if (query.kind === 'filter') {
			// Lite SQL filter from the search box, e.g. `panel = Radiology and not sent`.
			result = result.filter((p) => matchesFilter(query.filter, p));
		}
		if (field) {
			result = [...result].sort((a, b) => {
				if (field === 'arm' || field === 'tier' || field === 'size' || field === 'sle_after_mitigation') {
					const av = Number(a[field] ?? 0);
					const bv = Number(b[field] ?? 0);
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

	function toggleSort(field: keyof ProductRow) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}

	function toggleSelection(productId: string) {
		if (selectedProductIds.includes(productId)) {
			selectedProductIds = selectedProductIds.filter((id) => id !== productId);
		} else {
			selectedProductIds = [...selectedProductIds, productId];
		}
	}

	function toggleSelectAll() {
		if (allFilteredSelected) {
			const visible = new Set(filteredProducts.map((p) => p.id));
			selectedProductIds = selectedProductIds.filter((id) => !visible.has(id));
		} else {
			selectedProductIds = [...new Set([...selectedProductIds, ...filteredProducts.map((p) => p.id)])];
		}
	}

	// The model-risk page is the product's quantitative threat model; the
	// relationship is 1:1, so the row already carries the model id.
	function openModelRisk(modelId: number) {
		window.location.href = `/model-risk/${modelId}`;
	}

	function handleExperimentSelect(event: Event) {
		const target = event.currentTarget as HTMLSelectElement;
		const experimentId = target.value;
		if (!experimentId) return;
		// Carry the checked products into the experiment's Send to Close action.
		const query = selectedProductIds.length > 0 ? `?products=${selectedProductIds.join(',')}` : '';
		window.location.href = `/experiments/${experimentId}${query}`;
	}

	function closeAddModal() {
		showAddModal = false;
		newProduct = { submission_number: '', device: '', org_id: null };
		addModalError = null;
	}

	async function handleCreate() {
		try {
			addModalError = null;
			if (!newProduct.device || !newProduct.submission_number) {
				addModalError = 'Device and submission number are required';
				return;
			}
			const response = await fetch(`${apiBase}/products`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					submission_number: newProduct.submission_number,
					device: newProduct.device,
					org_id: newProduct.org_id
				})
			});
			if (!response.ok) throw new Error('Failed to create product');
			const created = await response.json();
			closeAddModal();
			window.location.href = `/products/${created.id}`;
		} catch (e) {
			addModalError = e instanceof Error ? e.message : 'Failed to create product';
		}
	}

	async function handleDelete(productId: string) {
		if (!confirm('Are you sure you want to delete this product?')) return;
		try {
			const response = await fetch(`${apiBase}/products/${productId}`, { method: 'DELETE' });
			if (!response.ok) throw new Error('Failed to delete product');
			products = products.filter(p => p.id !== productId);
			selectedProductIds = selectedProductIds.filter((id) => id !== productId);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete product';
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title page-title_row">
		<div class="input">
			<select
				id="start-experiment"
				class="input__text"
				class:input__text_changed={selectedProductIds.length > 0}
				onchange={handleExperimentSelect}
			>
				<option value="">Start experiment…</option>
				{#each experiments as experiment (experiment.id)}
					<option value={experiment.id}>{experiment.name}</option>
				{/each}
			</select>
			<label for="start-experiment" class="input__label">Experiment</label>
		</div>
		<button class="button button_green" onclick={() => (showAddModal = true)}>
			Add Product
		</button>
		<h1 class="heading heading_1">Products</h1>
	</div>

	<div class="grid-row">
		<div class="grid-col grid-col_24">
			<div class="studies card">
				<div class="card-header">
					<div class="heading heading_3">FDA devices</div>
				</div>

				{#if selectedProductIds.length > 0}
					<div class="list-status">
						<span class="list-status__text">
							{selectedProductIds.length}
							{selectedProductIds.length === 1 ? 'product' : 'products'} selected
							{#if hiddenSelectedCount > 0}
								({hiddenSelectedCount} hidden by the current filter)
							{/if}
							— choose an experiment above to continue.
						</span>
					</div>
				{/if}

				{#if productQuery.kind === 'error'}
					<div class="message message-error">Filter error: {productQuery.message}</div>
				{:else if productQuery.kind === 'text' && productQuery.warning}
					<div class="message message-warning">{productQuery.warning}</div>
				{:else if productQuery.kind === 'filter' && !loading}
					<div class="list-status">
						<span class="list-status__text">
							{#if filteredProducts.length === 0}
								Filter: {productQuery.filter.label} — no products match (0 of {products.length})
							{:else}
								Filter: {productQuery.filter.label} — {filteredProducts.length} of {products.length} products
							{/if}
						</span>
						<button type="button" class="button button_secondary button_s" onclick={() => globalSearch.clear()}>
							Clear filter
						</button>
					</div>
				{/if}

				{#if loading}
					<div class="message">Loading products...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredProducts.length === 0}
					{#if productQuery.kind !== 'filter'}
						<div class="message">No products found</div>
					{/if}
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal">
										<input
											type="checkbox"
											class="checkbox-input checkbox-input_inline"
											aria-label="Select all products"
											checked={allFilteredSelected}
											onchange={toggleSelectAll}
											onclick={(e) => e.stopPropagation()}
										/>
									</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'updated_at' && sortDirection === 'asc'} class:sorted-desc={sortField === 'updated_at' && sortDirection === 'desc'} onclick={() => toggleSort('updated_at')}>Updated</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'device' && sortDirection === 'asc'} class:sorted-desc={sortField === 'device' && sortDirection === 'desc'} onclick={() => toggleSort('device')}>Device</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'panel' && sortDirection === 'asc'} class:sorted-desc={sortField === 'panel' && sortDirection === 'desc'} onclick={() => toggleSort('panel')}>Panel</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'tag' && sortDirection === 'asc'} class:sorted-desc={sortField === 'tag' && sortDirection === 'desc'} onclick={() => toggleSort('tag')}>Tag</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'org_name' && sortDirection === 'asc'} class:sorted-desc={sortField === 'org_name' && sortDirection === 'desc'} onclick={() => toggleSort('org_name')}>Org</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'close_send_date' && sortDirection === 'asc'} class:sorted-desc={sortField === 'close_send_date' && sortDirection === 'desc'} onclick={() => toggleSort('close_send_date')}>Close Send Date</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'date_of_final_decision' && sortDirection === 'asc'} class:sorted-desc={sortField === 'date_of_final_decision' && sortDirection === 'desc'} onclick={() => toggleSort('date_of_final_decision')}>Final Decision</th>
									<th class="tal sortable table__hug" class:sorted-asc={sortField === 'sle_after_mitigation' && sortDirection === 'asc'} class:sorted-desc={sortField === 'sle_after_mitigation' && sortDirection === 'desc'} onclick={() => toggleSort('sle_after_mitigation')}>SLE after mitigation</th>
									<th class="tac table__actions">Actions</th>
								</tr>
							</thead>
							<tbody>
								{#each filteredProducts as p (p.id)}
									<tr class="entity-row" onclick={() => (window.location.href = `/products/${p.id}`)}>
										<td class="tal">
											<input
												type="checkbox"
												class="checkbox-input checkbox-input_inline"
												aria-label={`Select ${p.device}`}
												checked={selectedProductIds.includes(p.id)}
												onchange={() => toggleSelection(p.id)}
												onclick={(e) => e.stopPropagation()}
											/>
										</td>
										<td class="tal">{formatDate(p.updated_at) || '-'}</td>
										<td class="tal">{p.device}</td>
										<td class="tal">{p.panel || '-'}</td>
										<td class="tal">{p.tag || '-'}</td>
										<td class="tal">{p.org_name ?? '-'}</td>
										<td class="tal">{formatDate(p.close_send_date) || '-'}</td>
										<td class="tal">{formatDate(p.date_of_final_decision) || '-'}</td>
										<td class="tal table__hug">{p.sle_after_mitigation != null ? p.sle_after_mitigation.toLocaleString() : '-'}</td>
										<td class="tar table__actions">
											{#if p.model_id}
												<button class="button button_small" onclick={(e) => { e.stopPropagation(); openModelRisk(p.model_id!); }} title="Open model risk">
													<LineChart size={18} stroke-width={1.5} />
												</button>
											{/if}
											<button class="button button_small" onclick={(e) => { e.stopPropagation(); window.location.href = `/products/${p.id}/edit`; }} title="Edit">✎</button>
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
		<div class="modal-content" role="dialog" aria-labelledby="add-product-title" tabindex="0" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2 id="add-product-title" class="heading heading_2">Add Product</h2>
				<button type="button" class="modal-close" onclick={closeAddModal} title="Close">×</button>
			</div>
			<div class="modal-body">
				{#if addModalError}
					<div class="message message-error error-margin">Error: {addModalError}</div>
				{/if}
				<form onsubmit={(e) => { e.preventDefault(); handleCreate(); }}>
					<div class="input">
						<input id="add-device" type="text" bind:value={newProduct.device} class="input__text" class:input__text_changed={newProduct.device.length > 0} required />
						<label for="add-device" class="input__label">Device</label>
					</div>
					<div class="input">
						<input id="add-submission" type="text" bind:value={newProduct.submission_number} class="input__text" class:input__text_changed={newProduct.submission_number.length > 0} required />
						<label for="add-submission" class="input__label">Submission Number</label>
					</div>
					<div class="input input_select">
						<select id="add-org" bind:value={newProduct.org_id} class="input__text" class:input__text_changed={newProduct.org_id !== null}>
							<option value={null}>No organization</option>
							{#each orgs as o (o.id)}
								<option value={Number(o.id)}>{o.name}</option>
							{/each}
						</select>
						<label for="add-org" class="input__label">Organization</label>
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
