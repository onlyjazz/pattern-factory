<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import ThreatDetail from '$lib/ThreatDetail.svelte';

	let threat: any = null;
	let loading = true;
	let error: string | null = null;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const threatId = $page.params.id;
			const response = await fetch(`${apiBase}/threats/${threatId}`);
			if (!response.ok) throw new Error('Failed to fetch threat');
			const data = await response.json();
			threat = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function handleEdit() {
		if (threat?.id) {
			window.location.href = `/threats/${threat.id}/edit`;
		}
	}
</script>

<ThreatDetail
	{threat}
	{loading}
	{error}
	isEditing={false}
	onEdit={handleEdit}
/>
