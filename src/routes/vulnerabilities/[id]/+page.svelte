<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import VulnerabilityDetail from '$lib/VulnerabilityDetail.svelte';

	let vulnerability: any = null;
	let loading = true;
	let error: string | null = null;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const vulnerabilityId = $page.params.id;
			const response = await fetch(`${apiBase}/vulnerabilities/${vulnerabilityId}`);
			if (!response.ok) throw new Error('Failed to fetch vulnerability');
			const data = await response.json();
			vulnerability = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function handleEdit() {
		if (vulnerability?.id) {
			window.location.href = `/vulnerabilities/${vulnerability.id}/edit`;
		}
	}
</script>

<VulnerabilityDetail
	{vulnerability}
	{loading}
	{error}
	isEditing={false}
	onEdit={handleEdit}
/>
