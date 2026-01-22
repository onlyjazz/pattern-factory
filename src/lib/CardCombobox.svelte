<script lang="ts">
	import { onMount } from 'svelte';
	import SingleSelect from '$lib/SingleSelect.svelte';
	import type { SelectItem } from '$lib/SingleSelect.svelte';

	export let selectedCardId: string | null = null;
	export let selectedCardName: string = '';

	let cards: SelectItem[] = [];
	let loading: boolean = false;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			loading = true;
			const response = await fetch(`${apiBase}/cards`);
			if (!response.ok) throw new Error('Failed to fetch cards');
			cards = await response.json();
		} catch (error) {
			console.error('Error fetching cards:', error);
		} finally {
			loading = false;
		}
	});
</script>

<SingleSelect
	items={cards}
	bind:selectedId={selectedCardId}
	bind:selectedName={selectedCardName}
	placeholder="Search cards..."
	{loading}
/>
