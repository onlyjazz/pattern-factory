<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import CheckboxField from '$lib/CheckboxField.svelte';

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
					fixed_implementation_cost: countermeasure.fixed_implementation_cost || 0,
					fixed_cost_period: countermeasure.fixed_cost_period || 12,
					recurring_implementation_cost: countermeasure.recurring_implementation_cost || 0,
					include_fixed_cost: countermeasure.include_fixed_cost || true,
					include_recurring_cost: countermeasure.include_recurring_cost || true,
					implemented: countermeasure.implemented || false,
					disabled: countermeasure.disabled || false
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
						<div style="margin-bottom: 1.5rem; color: #666;">
							<strong>Version:</strong> {countermeasure.version || 1}
						</div>

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
							<h3>Cost Configuration</h3>
							<div class="input">
								<input
									id="fixed-implementation-cost"
									type="number"
									bind:value={countermeasure.fixed_implementation_cost}
									class="input__text"
									class:input__text_changed={countermeasure.fixed_implementation_cost}
									min="0"
								/>
								<label for="fixed-implementation-cost" class="input__label">Fixed Implementation Cost ($)</label>
							</div>

							<div class="input">
								<input
									id="fixed-cost-period"
									type="number"
									bind:value={countermeasure.fixed_cost_period}
									class="input__text"
									class:input__text_changed={countermeasure.fixed_cost_period}
									min="1"
								/>
								<label for="fixed-cost-period" class="input__label">Fixed Cost Period (months)</label>
							</div>

							<div class="input">
								<input
									id="recurring-implementation-cost"
									type="number"
									bind:value={countermeasure.recurring_implementation_cost}
									class="input__text"
									class:input__text_changed={countermeasure.recurring_implementation_cost}
									min="0"
								/>
								<label for="recurring-implementation-cost" class="input__label">Recurring Implementation Cost ($/year)</label>
							</div>
						</div>

						<div class="form-section">
							<h3>Cost Options</h3>
							<div style="margin-bottom: 1.5rem;">
								<CheckboxField
									id="include-fixed-cost"
									bind:checked={countermeasure.include_fixed_cost}
									label="Include fixed cost"
									description="When checked the risk assessment will include the fixed cost"
								/>
							</div>

							<div style="margin-bottom: 0;">
								<CheckboxField
									id="include-recurring-cost"
									bind:checked={countermeasure.include_recurring_cost}
									label="Include recurring cost"
									description="When checked the risk assessment will include the recurring cost on a yearly basis"
								/>
							</div>
						</div>

						<div class="form-section">
							<h3>Status</h3>
							<div style="margin-bottom: 1.5rem;">
								<CheckboxField
									id="implemented"
									bind:checked={countermeasure.implemented}
									label="Implemented"
									description="Check if you've already implemented this countermeasure"
								/>
							</div>

							<div style="margin-bottom: 0;">
								<CheckboxField
									id="disabled"
									bind:checked={countermeasure.disabled}
									label="Exclude"
									description="When clicking this checkbox, you will exclude the countermeasure from the risk mitigation set"
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
		<div class="message">Countermeasure not found</div>
	{/if}
</div>
