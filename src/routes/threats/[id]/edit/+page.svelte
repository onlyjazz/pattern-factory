<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { Threat } from '$lib/db';

	let threat: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const threatId = $page.params.id;
			const response = await fetch(`${apiBase}/threats/${threatId}`);
			if (!response.ok) throw new Error('Failed to fetch threat');
			const data = await response.json();
			threat = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	async function handleSave() {
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
					stride_category: threat.stride_category || null
				})
			});
			if (!response.ok) throw new Error('Failed to save threat');
			// Navigate back to view page
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

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Threat</h1>
	</div>

	{#if loading}
		<div class="message">Loading threat...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if threat}
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
									id="threat-name"
									type="text"
									bind:value={threat.name}
									class="input__text"
									class:input__text_changed={threat.name?.length > 0}
									required
								/>
								<label for="threat-name" class="input__label">Name</label>
							</div>

							<div class="input">
								<input
									id="threat-description"
									type="text"
									bind:value={threat.description}
									class="input__text"
									class:input__text_changed={threat.description?.length > 0}
									required
								/>
								<label for="threat-description" class="input__label">Description</label>
							</div>
						</div>

						<div class="form-section">
							<h3>Classification</h3>
							<div class="input input_select">
								<select
									id="threat-stride"
									bind:value={threat.stride_category}
									class="input__text"
									class:input__text_changed={threat.stride_category}
								>
									<option value="">Select STRIDE Category (Optional)</option>
									<option value="Spoofing">Spoofing</option>
									<option value="Tampering">Tampering</option>
									<option value="Repudiation">Repudiation</option>
									<option value="Information Disclosure">Information Disclosure</option>
									<option value="Denial of Service">Denial of Service</option>
									<option value="Elevation of Privilege">Elevation of Privilege</option>
								</select>
								<label for="threat-stride" class="input__label">STRIDE Category</label>
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
		<div class="message">Threat not found</div>
	{/if}
</div>
