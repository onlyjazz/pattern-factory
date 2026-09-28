<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import PersonDetail from '$lib/PersonDetail.svelte';
	import type { SelectItem } from '$lib/db';
	import { API_BASE } from '$lib/config';

	let person: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;
	let orgItems: SelectItem[] = [];
	let orgsLoading = false;
	let selectedOrgId: string | null = null;
	let selectedOrgName = '';

	const apiBase = API_BASE;

	async function loadOrgs() {
		try {
			orgsLoading = true;
			const response = await fetch(`${apiBase}/orgs`);
			if (!response.ok) throw new Error('Failed to fetch organizations');
			const data = await response.json();
			orgItems = data.map((o: any) => ({ id: String(o.id), name: o.name }));
		} catch (e) {
			console.error('Failed to load organizations:', e);
		} finally {
			orgsLoading = false;
		}
	}

	onMount(async () => {
		try {
			const personId = $page.params.id;
			const response = await fetch(`${apiBase}/people/${personId}`);
			if (!response.ok) throw new Error('Failed to fetch person');
			const data = await response.json();
			person = { ...data, id: String(data.id) };
			if (person.org_id) {
				selectedOrgId = String(person.org_id);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
		await loadOrgs();
		selectedOrgName = orgItems.find(o => o.id === selectedOrgId)?.name || '';
	});

	async function handleSave(e: Event) {
		if (!person) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/people/${person.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: person.name,
					description: person.description || null,
					job_description: person.job_description || null,
					linkedin_url: person.linkedin_url || null,
					email: person.email || null,
					company_url: person.company_url || null,
					content_source: person.content_source || null,
					content_url: person.content_url || null,
					org_id: selectedOrgId ? Number(selectedOrgId) : null
				})
			});
			if (!response.ok) throw new Error('Failed to save person');
			window.location.href = `/people/${person.id}`;
		} catch (err) {
			saveError = err instanceof Error ? err.message : 'Failed to save person';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (person?.id) {
			window.location.href = `/people/${person.id}`;
		}
	}
</script>

<PersonDetail
	{person}
	{loading}
	{error}
	{saveError}
	{isSaving}
	isEditing={true}
	{orgItems}
	{orgsLoading}
	bind:selectedOrgId
	bind:selectedOrgName
	onCancel={handleCancel}
	onSave={handleSave}
/>
