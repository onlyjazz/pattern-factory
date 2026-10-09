<script lang="ts">
	import { onMount } from 'svelte';
	import type { Experiment } from '$lib/types/models';
	import type { ProductOption } from '$lib/experiments';
	import { armLabel } from '$lib/experiments';
	import ProductMultiSelect from '$lib/ProductMultiSelect.svelte';
	import CloseSendResult from '$lib/CloseSendResult.svelte';
	import { startExperiment, type StartExperimentResult } from '$lib/closeSend';
	import { API_BASE } from '$lib/config';

	let experiments: Experiment[] = [];
	let products: ProductOption[] = [];
	let loading = true;
	let error: string | null = null;

	let selectedExperimentId: number | null = null;
	let selectedProductIds: number[] = [];
	let starting = false;
	let startError: string | null = null;
	let result: StartExperimentResult | null = null;

	const apiBase = API_BASE;

	// A step-less experiment cannot be activated: there is no channel content to pin.
	$: noSteps =
		selectedExperimentId !== null &&
		(experiments.find((e) => e.id === selectedExperimentId)?.steps?.length ?? 0) === 0;

	onMount(load);

	async function load() {
		try {
			loading = true;
			const [experimentsRes, productsRes] = await Promise.all([
				fetch(`${apiBase}/experiments`),
				fetch(`${apiBase}/products`)
			]);
			if (!experimentsRes.ok) throw new Error('Failed to fetch experiments');
			if (!productsRes.ok) throw new Error('Failed to fetch products');
			experiments = await experimentsRes.json();
			const productData: { id: number; device: string }[] = await productsRes.json();
			products = productData.map((p) => ({ id: Number(p.id), name: p.device }));
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	}

	function selectExperiment(id: number | null) {
		selectedExperimentId = id;
		result = null;
		startError = null;
		const experiment = experiments.find((e) => e.id === id);
		selectedProductIds = experiment?.product_ids ? [...experiment.product_ids] : [];
	}

	async function handleStart() {
		if (!selectedExperimentId) {
			startError = 'Select an experiment first';
			return;
		}
		if (noSteps) {
			startError = 'This experiment has no steps yet. Add at least one step on the experiment edit page.';
			return;
		}
		if (selectedProductIds.length === 0) {
			startError = 'Select at least one product';
			return;
		}
		try {
			starting = true;
			startError = null;
			result = null;
			result = await startExperiment(selectedExperimentId, selectedProductIds, apiBase);
		} catch (e) {
			startError = e instanceof Error ? e.message : 'Failed to start experiment';
		} finally {
			starting = false;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Start Experiment</h1>
	</div>

	{#if loading}
		<div class="message">Loading...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else}
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="studies card">
					<div class="card-header">
						<div class="heading heading_3">Choose an experiment</div>
					</div>
					<div class="input input_select">
						<select
							id="start-experiment"
							class="input__text"
							class:input__text_changed={selectedExperimentId !== null}
							onchange={(e) => selectExperiment(e.currentTarget.value ? Number(e.currentTarget.value) : null)}
						>
							<option value="">Select an experiment</option>
							{#each experiments as experiment (experiment.id)}
								<option value={experiment.id}>{experiment.name} — {armLabel(experiment.arm)}</option>
							{/each}
						</select>
						<label for="start-experiment" class="input__label">Experiment</label>
					</div>
				</div>

				<div class="studies card">
					<div class="card-header">
						<div class="heading heading_3">Products</div>
					</div>
					{#if noSteps}
						<div class="message message-error error-margin-v">
							This experiment has no steps yet. Add at least one step on the
							<a href={`/experiments/${selectedExperimentId}/edit`}>experiment edit page</a>
							before starting it.
						</div>
					{/if}
					<ProductMultiSelect items={products} bind:selectedIds={selectedProductIds} />

					{#if startError}
						<div class="message message-error error-margin-v">Error: {startError}</div>
					{/if}
					<CloseSendResult {result} />

					<div class="form-footer">
						<button type="button" class="button button_secondary" onclick={() => (window.location.href = '/products')}>
							Cancel
						</button>
						<button
							type="button"
							class="button button_green"
							onclick={handleStart}
							disabled={starting || !selectedExperimentId || selectedProductIds.length === 0 || noSteps}
						>
							{starting ? 'Starting...' : 'Start Experiment'}
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>
