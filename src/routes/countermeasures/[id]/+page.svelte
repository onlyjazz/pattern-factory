<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	let countermeasure: any = null;
	let loading = true;
	let error: string | null = null;

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

	function handleEdit() {
		if (countermeasure?.id) {
			window.location.href = `/countermeasures/${countermeasure.id}/edit`;
		}
	}
</script>

<div id="application-content-area">
	{#if loading}
		<div class="message">Loading countermeasure...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if countermeasure}
		<div class="entity-view-header">
			<div>
				<h1 class="heading heading_1">{countermeasure.name}</h1>
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
								<p>{countermeasure.name}</p>
							</div>
						</div>
						<div class="detail-row">
							<div class="detail-field full">
								<label>Description</label>
								<p>{countermeasure.description || '-'}</p>
							</div>
						</div>
						
						<!-- Yearly Cost (computed field) -->
						<div class="detail-row">
							<div class="detail-field">
								<label>Yearly Cost</label>
								<p>${countermeasure.yearly_cost || 0}</p>
							</div>
						</div>
						
						<!-- Cost Fields -->
						<div class="detail-row">
							<div class="detail-field">
								<label>Fixed Implementation Cost</label>
								<p>${countermeasure.fixed_implementation_cost || 0}</p>
							</div>
							<div class="detail-field">
								<label>Fixed Cost Period (months)</label>
								<p>{countermeasure.fixed_cost_period || 12}</p>
							</div>
						</div>
						<div class="detail-row">
							<div class="detail-field">
								<label>Recurring Implementation Cost</label>
								<p>${countermeasure.recurring_implementation_cost || 0}</p>
							</div>
						</div>
						
						<!-- Inclusion Flags -->
						<div class="detail-row">
							<div class="detail-field">
								<label>Include Fixed Cost</label>
								<p>{countermeasure.include_fixed_cost ? 'Yes' : 'No'}</p>
							</div>
							<div class="detail-field">
								<label>Include Recurring Cost</label>
								<p>{countermeasure.include_recurring_cost ? 'Yes' : 'No'}</p>
							</div>
						</div>
						
						<!-- Status Fields -->
						<div class="detail-row">
							<div class="detail-field">
								<label>Implemented</label>
								<p>{countermeasure.implemented ? 'Yes' : 'No'}</p>
							</div>
											<div class="detail-field">
												<label>Disabled</label>
												<p>{countermeasure.disabled ? 'Yes' : 'No'}</p>
											</div>
										</div>
										
										<!-- Version (metadata) -->
										<div class="detail-row">
											<div class="detail-field">
												<label>Version</label>
												<p>{countermeasure.version || 1}</p>
											</div>
										</div>
									</div>
								</div>
							</div>
		</div>
	{:else}
		<div class="message">Countermeasure not found</div>
	{/if}
</div>
