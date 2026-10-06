<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import OrgDetail from '$lib/OrgDetail.svelte';
	import type { SelectItem } from '$lib/db';
	import { API_BASE } from '$lib/config';

	let org: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;
	let statusItems: SelectItem[] = [];
	let statusesLoading = false;
	let selectedStatusId: string | null = null;
	let selectedStatusName = '';

	const apiBase = API_BASE;

	async function loadStatuses() {
		try {
			statusesLoading = true;
			const response = await fetch(`${apiBase}/statuses`);
			if (!response.ok) throw new Error('Failed to fetch statuses');
			const data = await response.json();
			statusItems = data.map((s: any) => ({ id: String(s.id), name: s.name }));
		} catch (e) {
			console.error('Failed to load statuses:', e);
		} finally {
			statusesLoading = false;
		}
	}

	onMount(async () => {
		try {
			const orgId = $page.params.id;
			const response = await fetch(`${apiBase}/orgs/${orgId}`);
			if (!response.ok) throw new Error('Failed to fetch organization');
			const data = await response.json();
			org = { ...data, id: String(data.id) };
			if (org.status_id) {
				selectedStatusId = String(org.status_id);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
		await loadStatuses();
		selectedStatusName = statusItems.find(s => s.id === selectedStatusId)?.name || '';
	});

	async function handleSave(e: Event) {
		if (!org) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/orgs/${org.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: org.name,
					name_before_acquisition: org.name_before_acquisition || null,
					description: org.description || null,
					stage: org.stage || null,
					funding: org.funding ?? null,
					estimated_annual_sales: org.estimated_annual_sales ?? null,
					// Always send the valuation so an explicit value survives a save that
					// also changes funding/sales (the PAT-371 trigger keys off the UPDATE
					// target list). See docs/ORG_SIZE_AND_SLE.md.
					size: org.size ?? null,
					employees: org.employees ?? null,
					headquarters: org.headquarters || null,
					arm: org.arm ?? null,
					study_arm: org.study_arm || null,
					date_founded: org.date_founded || null,
					linkedin_company_url: org.linkedin_company_url || null,
					status_id: selectedStatusId ? Number(selectedStatusId) : null
				})
			});
			if (!response.ok) throw new Error('Failed to save organization');
			window.location.href = `/orgs/${org.id}`;
		} catch (err) {
			saveError = err instanceof Error ? err.message : 'Failed to save organization';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (org?.id) {
			window.location.href = `/orgs/${org.id}`;
		}
	}
</script>

<OrgDetail
	{org}
	{loading}
	{error}
	{saveError}
	{isSaving}
	isEditing={true}
	{statusItems}
	{statusesLoading}
	bind:selectedStatusId
	bind:selectedStatusName
	onCancel={handleCancel}
	onSave={handleSave}
/>
