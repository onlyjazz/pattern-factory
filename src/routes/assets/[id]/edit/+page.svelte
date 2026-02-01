<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	let asset: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

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

	async function handleSave() {
		if (!asset) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/assets/${asset.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: asset.name,
					description: asset.description || null,
					asset_type: asset.asset_type || null,
					owner: asset.owner || null,
					tag: asset.tag || null
				})
			});
			if (!response.ok) throw new Error('Failed to save asset');
			// Navigate back to view page
			window.location.href = `/assets/${asset.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save asset';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (asset?.id) {
			window.location.href = `/assets/${asset.id}`;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Asset</h1>
	</div>

	{#if loading}
		<div class="message">Loading asset...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if asset}
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="entity-card">
					{#if saveError}
						<div class="message message-error" style="margin-bottom: 20px;">Error: {saveError}</div>
					{/if}

					<form onsubmit={(e) => {
						e.preventDefault();
						handleSave();
					}}>
						<div class="form-section">
							<h3>Basic Information</h3>
							<div class="input">
								<input
									id="asset-name"
									type="text"
									bind:value={asset.name}
									class="input__text"
									class:input__text_changed={asset.name?.length > 0}
									required
								/>
								<label for="asset-name" class="input__label">Name</label>
							</div>

							<div class="input">
								<input
									id="asset-description"
									type="text"
									bind:value={asset.description}
									class="input__text"
									class:input__text_changed={asset.description?.length > 0}
								/>
								<label for="asset-description" class="input__label">Description</label>
							</div>
						</div>

						<div class="form-section">
							<h3>Details</h3>
							<div class="input">
								<input
									id="asset-type"
									type="text"
									bind:value={asset.asset_type}
									class="input__text"
									class:input__text_changed={asset.asset_type?.length > 0}
								/>
								<label for="asset-type" class="input__label">Type</label>
							</div>

							<div class="input">
								<input
									id="asset-owner"
									type="text"
									bind:value={asset.owner}
									class="input__text"
									class:input__text_changed={asset.owner?.length > 0}
								/>
								<label for="asset-owner" class="input__label">Owner</label>
							</div>

							<div class="input">
								<input
									id="asset-tag"
									type="text"
									bind:value={asset.tag}
									class="input__text"
									class:input__text_changed={asset.tag?.length > 0}
								/>
								<label for="asset-tag" class="input__label">Tag</label>
							</div>
						</div>

						<div class="form-footer">
							<button
								type="button"
								class="button button_secondary"
								onclick={handleCancel}
								disabled={isSaving}
							>
								Cancel
							</button>
							<button type="submit" class="button button_green" disabled={isSaving}>
								{isSaving ? 'Saving...' : 'Save'}
							</button>
						</div>
					</form>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Asset not found</div>
	{/if}
</div>
