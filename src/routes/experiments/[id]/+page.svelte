<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import ExperimentDetail from '$lib/ExperimentDetail.svelte';
	import type { Experiment } from '$lib/types/models';
	import type { ProductOption } from '$lib/experiments';
	import { startExperiment, type StartExperimentResult } from '$lib/closeSend';
	import { API_BASE } from '$lib/config';

	let experiment: Experiment | null = null;
	let loading = true;
	let error: string | null = null;
	let productItems: ProductOption[] = [];
	let productsLoading = true;
	let sending = false;
	let sendError: string | null = null;
	let sendResult: StartExperimentResult | null = null;

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

	function handleEdit() {
		if (experiment?.id) {
			window.location.href = `/experiments/${experiment.id}/edit`;
		}
	}

	async function handleSend() {
		if (!experiment) return;
		try {
			sending = true;
			sendError = null;
			sendResult = null;
			sendResult = await startExperiment(experiment.id, experiment.product_ids, apiBase);
		} catch (e) {
			sendError = e instanceof Error ? e.message : 'Failed to start experiment';
		} finally {
			sending = false;
		}
	}
</script>

<ExperimentDetail
	{experiment}
	{loading}
	{error}
	isEditing={false}
	{productItems}
	{productsLoading}
	{sending}
	{sendError}
	{sendResult}
	onSend={handleSend}
	onEdit={handleEdit}
/>
