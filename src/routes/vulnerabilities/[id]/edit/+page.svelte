<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	let vulnerability: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const vulnerabilityId = $page.params.id;
			const response = await fetch(`${apiBase}/vulnerabilities/${vulnerabilityId}`);
			if (!response.ok) throw new Error('Failed to fetch vulnerability');
			const data = await response.json();
			vulnerability = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	async function handleSave() {
		if (!vulnerability) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/vulnerabilities/${vulnerability.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: vulnerability.name,
					description: vulnerability.description || null,
					severity: vulnerability.severity || null,
					cwe_id: vulnerability.cwe_id || null
				})
			});
			if (!response.ok) throw new Error('Failed to save vulnerability');
			// Navigate back to view page
			window.location.href = `/vulnerabilities/${vulnerability.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save vulnerability';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (vulnerability?.id) {
			window.location.href = `/vulnerabilities/${vulnerability.id}`;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Vulnerability</h1>
	</div>

	{#if loading}
		<div class="message">Loading vulnerability...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if vulnerability}
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
							<strong>Tag:</strong> V{vulnerability.id}
						</div>

						<div class="form-section">
							<h3>Basic Information</h3>
							<div class="input">
								<input
									id="vulnerability-name"
									type="text"
									bind:value={vulnerability.name}
									class="input__text"
									class:input__text_changed={vulnerability.name?.length > 0}
									required
								/>
								<label for="vulnerability-name" class="input__label">Name</label>
							</div>

							<div class="input">
								<input
									id="vulnerability-description"
									type="text"
									bind:value={vulnerability.description}
									class="input__text"
									class:input__text_changed={vulnerability.description?.length > 0}
								/>
								<label for="vulnerability-description" class="input__label">Description</label>
							</div>
						</div>

						<div class="form-section">
							<h3>Details</h3>
							<div class="input">
								<input
									id="vulnerability-severity"
									type="text"
									bind:value={vulnerability.severity}
									class="input__text"
									class:input__text_changed={vulnerability.severity?.length > 0}
								/>
								<label for="vulnerability-severity" class="input__label">Severity</label>
							</div>

							<div class="input">
								<input
									id="vulnerability-cwe"
									type="text"
									bind:value={vulnerability.cwe_id}
									class="input__text"
									class:input__text_changed={vulnerability.cwe_id?.length > 0}
								/>
								<label for="vulnerability-cwe" class="input__label">CWE ID</label>
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
		<div class="message">Vulnerability not found</div>
	{/if}
</div>
