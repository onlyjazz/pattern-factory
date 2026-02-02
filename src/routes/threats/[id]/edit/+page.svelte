<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import ThreatDetail from '$lib/ThreatDetail.svelte';
	import type { SelectItem } from '$lib/SingleSelect.svelte';

	let threat: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;
	let selectedCardId: string | null = null;
	let selectedCardName: string = '';
	let cardItems: SelectItem[] = [];
	let cardsLoading = false;

	const apiBase = 'http://localhost:8000';

	async function loadCards() {
		try {
			cardsLoading = true;
			const response = await fetch(`${apiBase}/cards`);
			if (!response.ok) throw new Error('Failed to fetch cards');
			cardItems = await response.json();
		} catch (e) {
			console.error('Failed to load cards:', e);
		} finally {
			cardsLoading = false;
		}
	}

	onMount(async () => {
		try {
			const threatId = $page.params.id;
			const response = await fetch(`${apiBase}/threats/${threatId}`);
			if (!response.ok) throw new Error('Failed to fetch threat');
			const data = await response.json();
			threat = { ...data, id: String(data.id) };
			if (threat.card) {
				selectedCardId = threat.card.id;
				selectedCardName = threat.card.name;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
		await loadCards();
	});

	async function handleSave(e: Event) {
		if (!threat) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/threats/${threat.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: threat.name,
					description: threat.description,
					domain: threat.domain || null,
					tag: threat.tag || null,
					damage_description: threat.damage_description || null,
					spoofing: threat.spoofing || false,
					tampering: threat.tampering || false,
					repudiation: threat.repudiation || false,
					information_disclosure: threat.information_disclosure || false,
					denial_of_service: threat.denial_of_service || false,
					elevation_of_privilege: threat.elevation_of_privilege || false,
					disabled: threat.disabled || false,
					card_id: selectedCardId || null
				})
			});
			if (!response.ok) throw new Error('Failed to save threat');
			window.location.href = `/threats/${threat.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save threat';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (threat?.id) {
			window.location.href = `/threats/${threat.id}`;
		}
	}
</script>

<ThreatDetail
	{threat}
	{loading}
	{error}
	{saveError}
	{isSaving}
	isEditing={true}
	{cardItems}
	{cardsLoading}
	{selectedCardId}
	{selectedCardName}
	onCancel={handleCancel}
	onSave={handleSave}
/>

<style>
	.card-selector-wrapper {
		margin-top: 24px;
	}

	.card-selector-wrapper h3 {
		margin: 0 0 12px 0;
	}
</style>
