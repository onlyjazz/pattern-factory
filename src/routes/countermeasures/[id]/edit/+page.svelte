<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import CountermeasureDetail from '$lib/CountermeasureDetail.svelte';

	let countermeasure: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const countermeasureId = $page.params.id;
			const response = await fetch(`${apiBase}/countermeasures/${countermeasureId}`);
			if (!response.ok) throw new Error('Failed to fetch countermeasure');
			const data = await response.json();
			countermeasure = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	async function handleSave(e: Event) {
		if (!countermeasure) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/countermeasures/${countermeasure.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: countermeasure.name,
					description: countermeasure.description || null,
					fixed_implementation_cost: countermeasure.fixed_implementation_cost || 0,
					fixed_cost_period: countermeasure.fixed_cost_period || 12,
					recurring_implementation_cost: countermeasure.recurring_implementation_cost || 0,
					include_fixed_cost: countermeasure.include_fixed_cost || true,
					include_recurring_cost: countermeasure.include_recurring_cost || true,
					implemented: countermeasure.implemented || false,
					disabled: countermeasure.disabled || false
				})
			});
			if (!response.ok) throw new Error('Failed to save countermeasure');
			window.location.href = `/countermeasures/${countermeasure.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save countermeasure';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (countermeasure?.id) {
			window.location.href = `/countermeasures/${countermeasure.id}`;
		}
	}
</script>

<CountermeasureDetail
	{countermeasure}
	{loading}
	{error}
	{saveError}
	{isSaving}
	isEditing={true}
	onCancel={handleCancel}
	onSave={handleSave}
/>
