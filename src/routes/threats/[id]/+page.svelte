<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { Threat } from '$lib/db';

	let threat: Threat | null = null;
	let loading = true;
	let error: string | null = null;

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

	function goToEdit() {
		if (threat?.id) {
			window.location.href = `/threats/${threat.id}/edit`;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Threats</h1>
	</div>

	{#if loading}
		<div class="message">Loading threat...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if threat}
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="entity-card">
					<div class="entity-view-header">
						<h2 class="heading heading_3">{threat.name}</h2>
						<button class="button button_green" onclick={goToEdit}>
							Edit
						</button>
					</div>

					<div class="detail-section">
						<h3>Basic Information</h3>
						<div class="detail-row">
							<div class="detail-field">
								<label>Description</label>
								<p>{threat.description}</p>
							</div>
						</div>
					</div>

					<div class="detail-section">
						<h3>Threat Metrics</h3>
						<div class="detail-row">
							<div class="detail-field">
								<label>Probability</label>
								<p>{threat.probability || '-'}</p>
							</div>
							<div class="detail-field">
								<label>Mitigation Level</label>
								<p>{threat.mitigation_level || '-'}</p>
							</div>
							<div class="detail-field">
								<label>Disabled</label>
								<p>{threat.disabled ? 'Yes' : 'No'}</p>
							</div>
						</div>
						<div class="detail-row full">
							<div class="detail-field">
								<label>Damage Description</label>
								<p>{threat.damage_description || '-'}</p>
							</div>
						</div>
					</div>

					<div class="detail-section">
						<h3>STRIDE Classification</h3>
						<div class="detail-row">
							<div class="detail-field">
								<label>Spoofing</label>
								<p>{threat.spoofing ? '✓' : '✗'}</p>
							</div>
							<div class="detail-field">
								<label>Tampering</label>
								<p>{threat.tampering ? '✓' : '✗'}</p>
							</div>
							<div class="detail-field">
								<label>Repudiation</label>
								<p>{threat.repudiation ? '✓' : '✗'}</p>
							</div>
							<div class="detail-field">
								<label>Info Disclosure</label>
								<p>{threat.information_disclosure ? '✓' : '✗'}</p>
							</div>
							<div class="detail-field">
								<label>Denial of Service</label>
								<p>{threat.denial_of_service ? '✓' : '✗'}</p>
							</div>
							<div class="detail-field">
								<label>Elevation of Privilege</label>
								<p>{threat.elevation_of_privilege ? '✓' : '✗'}</p>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Threat not found</div>
	{/if}
</div>
