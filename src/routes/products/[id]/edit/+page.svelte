<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import ProductDetail from '$lib/ProductDetail.svelte';
	import type { SelectItem } from '$lib/db';
	import { API_BASE } from '$lib/config';

	let product: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;
	let orgItems: SelectItem[] = [];
	let orgsLoading = false;
	let selectedOrgId: string | null = null;
	let selectedOrgName = '';

	const apiBase = API_BASE;

	async function loadOrgs() {
		try {
			orgsLoading = true;
			const response = await fetch(`${apiBase}/orgs`);
			if (!response.ok) throw new Error('Failed to fetch organizations');
			const data = await response.json();
			orgItems = data.map((o: any) => ({ id: String(o.id), name: o.name }));
		} catch (e) {
			console.error('Failed to load organizations:', e);
		} finally {
			orgsLoading = false;
		}
	}

	onMount(async () => {
		try {
			const productId = $page.params.id;
			const response = await fetch(`${apiBase}/products/${productId}`);
			if (!response.ok) throw new Error('Failed to fetch product');
			const data = await response.json();
			product = { ...data, id: String(data.id) };
			if (product.org_id) {
				selectedOrgId = String(product.org_id);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
		await loadOrgs();
		selectedOrgName = orgItems.find(o => o.id === selectedOrgId)?.name || '';
	});

	async function handleSave(e: Event) {
		if (!product) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/products/${product.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					submission_number: product.submission_number,
					device: product.device,
					company: product.company || null,
					panel: product.panel || null,
					primary_product_code: product.primary_product_code || null,
					date_of_final_decision: product.date_of_final_decision || null,
					intended_use: product.intended_use || null,
					indications_for_use: product.indications_for_use || null,
					device_description: product.device_description || null,
					superiority: product.superiority || null,
					competitors: product.competitors || null,
					product_contact_1: product.product_contact_1 || null,
					product_contact_2: product.product_contact_2 || null,
					product_contact_3: product.product_contact_3 || null,
					org_id: selectedOrgId ? Number(selectedOrgId) : null,
					process_flag: product.process_flag || false
				})
			});
			if (!response.ok) throw new Error('Failed to save product');
			window.location.href = `/products/${product.id}`;
		} catch (err) {
			saveError = err instanceof Error ? err.message : 'Failed to save product';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (product?.id) {
			window.location.href = `/products/${product.id}`;
		}
	}
</script>

<ProductDetail
	{product}
	{loading}
	{error}
	{saveError}
	{isSaving}
	isEditing={true}
	{orgItems}
	{orgsLoading}
	bind:selectedOrgId
	bind:selectedOrgName
	onCancel={handleCancel}
	onSave={handleSave}
/>
