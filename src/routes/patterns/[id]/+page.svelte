<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { Pattern } from '$lib/db';

	let pattern: Pattern | null = null;
	let loading = true;
	let error: string | null = null;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const patternId = $page.params.id;
			const response = await fetch(`${apiBase}/patterns/${patternId}`);
			if (!response.ok) throw new Error('Failed to fetch pattern');
			const data = await response.json();
			pattern = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function goToEdit() {
		if (pattern?.id) {
			window.location.href = `/patterns/${pattern.id}/edit`;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Patterns</h1>
	</div>

	{#if loading}
		<div class="message">Loading pattern...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if pattern}
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="entity-card">
					<div class="entity-view-header">
						<h2 class="heading heading_3">{pattern.name}</h2>
						<button class="button button_green" onclick={goToEdit}>
							Edit
						</button>
					</div>

					<div class="detail-section">
						<h3>Basic Information</h3>
						<div class="detail-row">
							<div class="detail-field">
								<label>Description</label>
								<p>{pattern.description}</p>
							</div>
							<div class="detail-field">
								<label>Kind</label>
								<p>{pattern.kind}</p>
							</div>
						</div>
						<div class="detail-row full">
							<div class="detail-field">
								<label>Taxonomy</label>
								<p>{pattern.taxonomy || '-'}</p>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Pattern not found</div>
	{/if}
</div>
