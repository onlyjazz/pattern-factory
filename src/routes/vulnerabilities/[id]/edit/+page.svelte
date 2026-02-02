<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import VulnerabilityDetail from '$lib/VulnerabilityDetail.svelte';

	let vulnerability: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

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

	async function handleSave(e: Event) {
		if (!vulnerability) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/vulnerabilities/${vulnerability.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: vulnerability.name,
					description: vulnerability.description || null,
					disabled: vulnerability.disabled || false
				})
			});
			if (!response.ok) throw new Error('Failed to save vulnerability');
			window.location.href = `/vulnerabilities/${vulnerability.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save vulnerability';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (vulnerability?.id) {
			window.location.href = `/vulnerabilities/${vulnerability.id}`;
		}
	}
</script>

<VulnerabilityDetail
	{vulnerability}
	{loading}
	{error}
	{saveError}
	{isSaving}
	isEditing={true}
	onCancel={handleCancel}
		onSave={handleSave}
/>
