<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { Card } from '$lib/db';

	let card: Card | null = null;
	let loading = true;
	let error: string | null = null;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const cardId = $page.params.id;
			const response = await fetch(`${apiBase}/cards/${cardId}`);
			if (!response.ok) throw new Error('Failed to fetch card');
			const data = await response.json();
			card = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function goToEdit() {
		if (card?.id) {
			window.location.href = `/cards/${card.id}/edit`;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Cards</h1>
	</div>

	{#if loading}
		<div class="message">Loading card...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if card}
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="entity-card">
					<div class="entity-view-header">
						<h2 class="heading heading_3">{card.name}</h2>
						<button class="button button_green" onclick={goToEdit}>
							Edit
						</button>
					</div>

					<div class="detail-section">
						<h3>Basic Information</h3>
						<div class="detail-row">
							<div class="detail-field">
								<label>Description</label>
								<p>{card.description}</p>
							</div>
							<div class="detail-field">
								<label>Pattern</label>
								<p>{card.pattern_name || '-'}</p>
							</div>
						</div>
					</div>

					<div class="detail-section">
						<h3>Details</h3>
						<div class="detail-row">
							<div class="detail-field">
								<label>Order Index</label>
								<p>{card.order_index || '-'}</p>
							</div>
							<div class="detail-field">
								<label>Domain</label>
								<p>{card.domain || '-'}</p>
							</div>
							<div class="detail-field">
								<label>Audience</label>
								<p>{card.audience || '-'}</p>
							</div>
							<div class="detail-field">
								<label>Maturity</label>
								<p>{card.maturity || '-'}</p>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Card not found</div>
	{/if}
</div>
