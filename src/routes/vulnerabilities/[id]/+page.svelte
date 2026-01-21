<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	let vulnerability: any = null;
	let loading = true;
	let error: string | null = null;

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

	function handleEdit() {
		if (vulnerability?.id) {
			window.location.href = `/vulnerabilities/${vulnerability.id}/edit`;
		}
	}
</script>

<div id="application-content-area">
	{#if loading}
		<div class="message">Loading vulnerability...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if vulnerability}
		<div class="entity-view-header">
			<div>
				<h1 class="heading heading_1">{vulnerability.name}</h1>
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
								<p>{vulnerability.name}</p>
							</div>
						</div>
						<div class="detail-row">
							<div class="detail-field full">
								<label>Description</label>
								<p>{vulnerability.description || '-'}</p>
							</div>
						</div>
						{#if vulnerability.severity}
							<div class="detail-row">
								<div class="detail-field">
									<label>Severity</label>
									<p>{vulnerability.severity}</p>
								</div>
							</div>
						{/if}
						{#if vulnerability.cwe_id}
							<div class="detail-row">
								<div class="detail-field">
									<label>CWE ID</label>
									<p>{vulnerability.cwe_id}</p>
								</div>
							</div>
						{/if}
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Vulnerability not found</div>
	{/if}
</div>
