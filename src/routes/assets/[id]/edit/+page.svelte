<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import AssetDetail from '$lib/AssetDetail.svelte';

	let asset: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const assetId = $page.params.id;
			const response = await fetch(`${apiBase}/assets/${assetId}`);
			if (!response.ok) throw new Error('Failed to fetch asset');
			const data = await response.json();
			asset = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	async function handleSave(e: Event) {
		if (!asset) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/assets/${asset.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: asset.name,
					description: asset.description || null,
					tag: asset.tag || null,
					fixed_value: asset.fixed_value || 0,
					fixed_value_period: asset.fixed_value_period || 12,
					recurring_value: asset.recurring_value || 0,
					include_fixed_value: asset.include_fixed_value || true,
					include_recurring_value: asset.include_recurring_value || true
				})
			});
			if (!response.ok) throw new Error('Failed to save asset');
			window.location.href = `/assets/${asset.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save asset';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (asset?.id) {
			window.location.href = `/assets/${asset.id}`;
		}
	}
</script>

<AssetDetail
	{asset}
	{loading}
	{error}
	{saveError}
	{isSaving}
	isEditing={true}
	onCancel={handleCancel}
	onSave={handleSave}
/>
