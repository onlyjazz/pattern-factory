<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import ProductDetail from '$lib/ProductDetail.svelte';
	import { API_BASE } from '$lib/config';

	let product: any = null;
	let loading = true;
	let error: string | null = null;
	let selectedOrgId: string | null = null;
	let selectedOrgName = '';

	const apiBase = API_BASE;

	onMount(async () => {
		try {
			const productId = $page.params.id;
			const response = await fetch(`${apiBase}/products/${productId}`);
			if (!response.ok) throw new Error('Failed to fetch product');
			const data = await response.json();
			product = { ...data, id: String(data.id) };
			if (product.org_id) {
				selectedOrgId = String(product.org_id);
				const orgRes = await fetch(`${apiBase}/orgs/${product.org_id}`);
				if (orgRes.ok) {
					const org = await orgRes.json();
					selectedOrgName = org.name || '';
				}
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function handleEdit() {
		if (product?.id) {
			window.location.href = `/products/${product.id}/edit`;
		}
	}
</script>

<ProductDetail
	{product}
	{loading}
	{error}
	isEditing={false}
	{selectedOrgId}
	{selectedOrgName}
	onEdit={handleEdit}
/>
