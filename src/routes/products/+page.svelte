<script lang="ts">
	import { onMount } from 'svelte';
	import { globalSearch } from '$lib/searchStore';
	import type { Product, Organization } from '$lib/db';
	import { API_BASE } from '$lib/config';

	let products: Product[] = [];
	let orgs: Organization[] = [];
	let loading = true;
	let error: string | null = null;
	let filteredProducts: Product[] = [];

	let showAddModal = false;
	let addModalError: string | null = null;
	let newProduct = { submission_number: '', device: '', company: '', org_id: null as number | null };

	let sortField: keyof Product | null = 'device';
	let sortDirection: 'asc' | 'desc' = 'asc';

	const apiBase = API_BASE;

	$: filteredProducts = filterProducts(products, $globalSearch, sortField, sortDirection);

	onMount(async () => {
		try {
			const [productsRes, orgsRes] = await Promise.all([
				fetch(`${apiBase}/products`),
				fetch(`${apiBase}/orgs`)
			]);
			if (!productsRes.ok) throw new Error('Failed to fetch products');
			const data = await productsRes.json();
			products = data.map((p: any) => ({ ...p, id: String(p.id) }));
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

	function filterProducts(items: Product[], search: string, field: keyof Product | null, dir: 'asc' | 'desc'): Product[] {
		let result = items;
		if (search.trim() !== '') {
			const term = search.toLowerCase();
			result = result.filter(p =>
				(p.device || '').toLowerCase().includes(term) ||
				(p.submission_number || '').toLowerCase().includes(term) ||
				(p.company || '').toLowerCase().includes(term) ||
				(p.panel || '').toLowerCase().includes(term)
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

	function toggleSort(field: keyof Product) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}

	function closeAddModal() {
		showAddModal = false;
		newProduct = { submission_number: '', device: '', company: '', org_id: null };
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
					company: newProduct.company || null,
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
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to delete product';
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
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

				{#if loading}
					<div class="message">Loading products...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else if filteredProducts.length === 0}
					<div class="message">No products found</div>
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal sortable" class:sorted-asc={sortField === 'submission_number' && sortDirection === 'asc'} class:sorted-desc={sortField === 'submission_number' && sortDirection === 'desc'} onclick={() => toggleSort('submission_number')}>Submission</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'device' && sortDirection === 'asc'} class:sorted-desc={sortField === 'device' && sortDirection === 'desc'} onclick={() => toggleSort('device')}>Device</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'company' && sortDirection === 'asc'} class:sorted-desc={sortField === 'company' && sortDirection === 'desc'} onclick={() => toggleSort('company')}>Company</th>
									<th class="tal sortable" class:sorted-asc={sortField === 'panel' && sortDirection === 'asc'} class:sorted-desc={sortField === 'panel' && sortDirection === 'desc'} onclick={() => toggleSort('panel')}>Panel</th>
									<th class="tal">Org</th>
									<th class="tar">Actions</th>
								</tr>
							</thead>
							<tbody>
								{#each filteredProducts as p (p.id)}
									<tr class="entity-row" onclick={() => (window.location.href = `/products/${p.id}`)}>
										<td class="tal">{p.submission_number || '-'}</td>
										<td class="tal">{p.device}</td>
										<td class="tal">{p.company || '-'}</td>
										<td class="tal">{p.panel || '-'}</td>
										<td class="tal">{orgName(p.org_id)}</td>
										<td class="tar">
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
					<div class="input">
						<input id="add-company" type="text" bind:value={newProduct.company} class="input__text" class:input__text_changed={newProduct.company.length > 0} />
						<label for="add-company" class="input__label">Company</label>
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
