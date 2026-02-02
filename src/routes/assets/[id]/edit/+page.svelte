<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import CheckboxField from '$lib/CheckboxField.svelte';

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
					tag: asset.tag || null,
					fixed_value: asset.fixed_value || 0,
					fixed_value_period: asset.fixed_value_period || 12,
					recurring_value: asset.recurring_value || 0,
					include_fixed_value: asset.include_fixed_value || true,
					include_recurring_value: asset.include_recurring_value || true
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
						<div style="margin-bottom: 1.5rem; color: #666;">
							<strong>Version:</strong> {asset.version || 1}
						</div>

						<div style="margin-bottom: 1.5rem; color: #666;">
							<strong>Yearly Value (Computed):</strong> {asset.yearly_value || 0}
						</div>

						<div class="form-section">
							<h3>Basic Information</h3>
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
							<h3>Financial Configuration</h3>
							<div class="input">
								<input
									id="fixed-value"
									type="number"
									bind:value={asset.fixed_value}
									class="input__text"
									class:input__text_changed={asset.fixed_value}
									min="0"
								/>
								<label for="fixed-value" class="input__label">Fixed Value ($)</label>
							</div>

							<div class="input">
								<input
									id="fixed-value-period"
									type="number"
									bind:value={asset.fixed_value_period}
									class="input__text"
									class:input__text_changed={asset.fixed_value_period}
									min="1"
								/>
								<label for="fixed-value-period" class="input__label">Fixed Value Period (months)</label>
							</div>

							<div class="input">
								<input
									id="recurring-value"
									type="number"
									bind:value={asset.recurring_value}
									class="input__text"
									class:input__text_changed={asset.recurring_value}
									min="0"
								/>
								<label for="recurring-value" class="input__label">Recurring Value ($/year)</label>
							</div>
						</div>

						<div class="form-section">
							<h3>Include Options</h3>
							<div style="margin-bottom: 1.5rem;">
								<CheckboxField
									id="include-fixed-value"
									bind:checked={asset.include_fixed_value}
									label="Include fixed value"
									description="When checked the yearly value will include the fixed value"
								/>
							</div>

							<div style="margin-bottom: 0;">
								<CheckboxField
									id="include-recurring-value"
									bind:checked={asset.include_recurring_value}
									label="Include recurring value"
									description="When checked the yearly value will include the recurring value"
								/>
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
