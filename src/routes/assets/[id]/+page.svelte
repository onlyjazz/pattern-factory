<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	let asset: any = null;
	let loading = true;
	let error: string | null = null;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const assetId = $page.params.id;
			const response = await fetch(`${apiBase}/assets/${assetId}`);
			if (!response.ok) throw new Error('Failed to fetch asset');
			const data = await response.json();
			asset = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function handleEdit() {
		if (asset?.id) {
			window.location.href = `/assets/${asset.id}/edit`;
		}
	}
</script>

<div id="application-content-area">
	{#if loading}
		<div class="message">Loading asset...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if asset}
		<div class="entity-view-header">
			<div>
				<h1 class="heading heading_1">{asset.name}</h1>
			</div>
			<button class="button button_green" onclick={handleEdit}>
				EDIT
			</button>
		</div>

		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="entity-card">
					<div class="detail-section">
						<div class="detail-row">
							<div class="detail-field">
								<label>Name</label>
								<p>{asset.name}</p>
							</div>
						</div>
						<div class="detail-row">
							<div class="detail-field full">
								<label>Description</label>
								<p>{asset.description || '-'}</p>
							</div>
						</div>
						{#if asset.asset_type}
							<div class="detail-row">
								<div class="detail-field">
									<label>Type</label>
									<p>{asset.asset_type}</p>
								</div>
							</div>
						{/if}
						{#if asset.owner}
							<div class="detail-row">
								<div class="detail-field">
									<label>Owner</label>
									<p>{asset.owner}</p>
								</div>
							</div>
						{/if}
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Asset not found</div>
	{/if}
</div>
