<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import PersonDetail from '$lib/PersonDetail.svelte';
	import { API_BASE } from '$lib/config';

	let person: any = null;
	let loading = true;
	let error: string | null = null;
	let selectedOrgId: string | null = null;
	let selectedOrgName = '';

	const apiBase = API_BASE;

	onMount(async () => {
		try {
			const personId = $page.params.id;
			const response = await fetch(`${apiBase}/people/${personId}`);
			if (!response.ok) throw new Error('Failed to fetch person');
			const data = await response.json();
			person = { ...data, id: String(data.id) };
			if (person.org_id) {
				selectedOrgId = String(person.org_id);
				const orgRes = await fetch(`${apiBase}/orgs/${person.org_id}`);
				if (orgRes.ok) {
					const org = await orgRes.json();
					selectedOrgName = org.name || '';
				}
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function handleEdit() {
		if (person?.id) {
			window.location.href = `/people/${person.id}/edit`;
		}
	}
</script>

<PersonDetail
	{person}
	{loading}
	{error}
	isEditing={false}
	{selectedOrgId}
	{selectedOrgName}
	onEdit={handleEdit}
/>
