<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import ExperimentDetail from '$lib/ExperimentDetail.svelte';
	import type { Experiment } from '$lib/types/models';
	import type { ProductOption } from '$lib/experiments';
	import { API_BASE } from '$lib/config';

	let experiment: Experiment | null = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;
	let productItems: ProductOption[] = [];
	let productsLoading = true;

	const apiBase = API_BASE;

	onMount(async () => {
		const experimentId = $page.params.id;
		try {
			const response = await fetch(`${apiBase}/experiments/${experimentId}`);
			if (!response.ok) throw new Error('Failed to fetch experiment');
			const data: Experiment = await response.json();
			experiment = {
				...data,
				steps: data.steps ?? [],
				product_ids: data.product_ids ?? []
			};
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
		await loadProducts();
	});

	async function loadProducts() {
		try {
			const response = await fetch(`${apiBase}/products`);
			if (!response.ok) throw new Error('Failed to fetch products');
			const data: { id: number; device: string }[] = await response.json();
			productItems = data.map((p) => ({ id: Number(p.id), name: p.device }));
		} catch (e) {
			console.error('Failed to load products:', e);
		} finally {
			productsLoading = false;
		}
	}

	async function handleSave(e: Event) {
		if (!experiment) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/experiments/${experiment.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: experiment.name,
					description: experiment.description || null,
					arm: experiment.arm,
					email_header: experiment.email_header || null,
					email_header_status: experiment.email_header_status,
					steps: (experiment.steps ?? []).map((step, i) => ({ ...step, position: i + 1 })),
					product_ids: experiment.product_ids ?? []
				})
			});
			if (!response.ok) throw new Error('Failed to save experiment');
			window.location.href = `/experiments/${experiment.id}`;
		} catch (err) {
			saveError = err instanceof Error ? err.message : 'Failed to save experiment';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (experiment?.id) {
			window.location.href = `/experiments/${experiment.id}`;
		}
	}
</script>

<ExperimentDetail
	{experiment}
	{loading}
	{error}
	{saveError}
	{isSaving}
	isEditing={true}
	{productItems}
	{productsLoading}
	onCancel={handleCancel}
	onSave={handleSave}
/>
