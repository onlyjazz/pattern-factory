<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import OrgDetail from '$lib/OrgDetail.svelte';
	import { API_BASE } from '$lib/config';

	let org: any = null;
	let loading = true;
	let error: string | null = null;
	let selectedStatusId: string | null = null;
	let selectedStatusName = '';

	const apiBase = API_BASE;

	onMount(async () => {
		try {
			const orgId = $page.params.id;
			const response = await fetch(`${apiBase}/orgs/${orgId}`);
			if (!response.ok) throw new Error('Failed to fetch organization');
			const data = await response.json();
			org = { ...data, id: String(data.id) };
			if (org.status_id) {
				selectedStatusId = String(org.status_id);
				const statusesRes = await fetch(`${apiBase}/statuses`);
				if (statusesRes.ok) {
					const statuses = await statusesRes.json();
					const match = statuses.find((s: any) => s.id === org.status_id);
					selectedStatusName = match ? match.name : '';
				}
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function handleEdit() {
		if (org?.id) {
			window.location.href = `/orgs/${org.id}/edit`;
		}
	}
</script>

<OrgDetail
	{org}
	{loading}
	{error}
	isEditing={false}
	{selectedStatusId}
	{selectedStatusName}
	onEdit={handleEdit}
/>
