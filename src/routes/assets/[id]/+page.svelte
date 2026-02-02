<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import AssetDetail from '$lib/AssetDetail.svelte';

	let asset: any = null;
	let loading = true;
	let error: string | null = null;

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

	function handleEdit() {
		if (asset?.id) {
			window.location.href = `/assets/${asset.id}/edit`;
		}
	}
</script>

<AssetDetail
	{asset}
	{loading}
	{error}
	isEditing={false}
	onEdit={handleEdit}
/>
