<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import CountermeasureDetail from '$lib/CountermeasureDetail.svelte';

	let countermeasure: any = null;
	let loading = true;
	let error: string | null = null;

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

	function handleEdit() {
		if (countermeasure?.id) {
			window.location.href = `/countermeasures/${countermeasure.id}/edit`;
		}
	}
</script>

<CountermeasureDetail
	{countermeasure}
	{loading}
	{error}
	isEditing={false}
	onEdit={handleEdit}
|/>
