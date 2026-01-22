<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import CheckboxField from '$lib/CheckboxField.svelte';
	import CardCombobox from '$lib/CardCombobox.svelte';
	import type { Threat } from '$lib/db';

	let threat: any = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;
	let selectedCardId: string | null = null;
	let selectedCardName: string = '';

	const apiBase = 'http://localhost:8000';

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
						<div class="card-selector-wrapper">
							<h3>Associated Card</h3>
							<CardCombobox
								bind:selectedCardId
								bind:selectedCardName
							/>
						</div>
					</div>

						<div class="form-section">
							<h3>STRIDE Classifications</h3>
							<div class="stride-grid">
								<CheckboxField
									id="threat-spoofing"
									bind:checked={threat.spoofing}
									label="Spoofing"
								/>
								<CheckboxField
									id="threat-tampering"
									bind:checked={threat.tampering}
									label="Tampering"
								/>
								<CheckboxField
									id="threat-repudiation"
									bind:checked={threat.repudiation}
									label="Repudiation"
								/>
								<CheckboxField
									id="threat-information-disclosure"
									bind:checked={threat.information_disclosure}
									label="Information Disclosure"
								/>
								<CheckboxField
									id="threat-denial-of-service"
									bind:checked={threat.denial_of_service}
									label="Denial of Service"
								/>
								<CheckboxField
									id="threat-elevation-of-privilege"
									bind:checked={threat.elevation_of_privilege}
									label="Elevation of Privilege"
								/>
							</div>
						</div>

						<div class="form-section">
							<CheckboxField
								id="threat-disabled"
								bind:checked={threat.disabled}
								label="Disable the threat"
								description="When clicking this checkbox, you disable the threat from the model"
							/>
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

<style>
	.card-selector-wrapper {
		margin-top: 24px;
	}

	.card-selector-wrapper h3 {
		margin: 0 0 12px 0;
	}
</style>
