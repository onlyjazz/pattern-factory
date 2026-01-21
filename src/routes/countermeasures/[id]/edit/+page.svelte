<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	let countermeasure: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const countermeasureId = $page.params.id;
			const response = await fetch(`${apiBase}/countermeasures/${countermeasureId}`);
			if (!response.ok) throw new Error('Failed to fetch countermeasure');
			const data = await response.json();
			countermeasure = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	async function handleSave() {
		if (!countermeasure) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/countermeasures/${countermeasure.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: countermeasure.name,
					description: countermeasure.description || null,
					implementation_level: countermeasure.implementation_level || null,
					cost: countermeasure.cost || null
				})
			});
			if (!response.ok) throw new Error('Failed to save countermeasure');
			// Navigate back to view page
			window.location.href = `/countermeasures/${countermeasure.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save countermeasure';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (countermeasure?.id) {
			window.location.href = `/countermeasures/${countermeasure.id}`;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Countermeasure</h1>
	</div>

	{#if loading}
		<div class="message">Loading countermeasure...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if countermeasure}
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
									id="countermeasure-name"
									type="text"
									bind:value={countermeasure.name}
									class="input__text"
									class:input__text_changed={countermeasure.name?.length > 0}
									required
								/>
								<label for="countermeasure-name" class="input__label">Name</label>
							</div>

							<div class="input">
								<input
									id="countermeasure-description"
									type="text"
									bind:value={countermeasure.description}
									class="input__text"
									class:input__text_changed={countermeasure.description?.length > 0}
								/>
								<label for="countermeasure-description" class="input__label">Description</label>
							</div>
						</div>

						<div class="form-section">
							<h3>Details</h3>
							<div class="input">
								<input
									id="countermeasure-implementation"
									type="text"
									bind:value={countermeasure.implementation_level}
									class="input__text"
									class:input__text_changed={countermeasure.implementation_level?.length > 0}
								/>
								<label for="countermeasure-implementation" class="input__label">Implementation Level</label>
							</div>

							<div class="input">
								<input
									id="countermeasure-cost"
									type="text"
									bind:value={countermeasure.cost}
									class="input__text"
									class:input__text_changed={countermeasure.cost?.length > 0}
								/>
								<label for="countermeasure-cost" class="input__label">Cost</label>
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
		<div class="message">Countermeasure not found</div>
	{/if}
</div>
