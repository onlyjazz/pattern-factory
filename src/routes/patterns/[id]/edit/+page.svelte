<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { Pattern } from '$lib/db';

	let pattern: Pattern | null = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

	const apiBase = 'http://localhost:8000';
	const kinds = ['pattern', 'anti-pattern'];
	const taxonomyOptions = [
		'',
		'Category Anti-Pattern',
		'Regulatory / GTM Anti-Pattern',
		'Founder / Financing Anti-Pattern',
		'Demand Formation Anti-Pattern',
		'Decision & Cognitive Accelerator'
	];

	onMount(async () => {
		try {
			const patternId = $page.params.id;
			const response = await fetch(`${apiBase}/patterns/${patternId}`);
			if (!response.ok) throw new Error('Failed to fetch pattern');
			const data = await response.json();
			pattern = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	async function handleSave() {
		if (!pattern) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/patterns/${pattern.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: pattern.name,
					description: pattern.description,
					kind: pattern.kind,
					story_md: pattern.story_md || null,
					taxonomy: pattern.taxonomy || null
				})
			});
			if (!response.ok) throw new Error('Failed to save pattern');
			// Navigate back to view page
			window.location.href = `/patterns/${pattern.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save pattern';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (pattern?.id) {
			window.location.href = `/patterns/${pattern.id}`;
		}
	}

	function goToStoryEditor() {
		if (pattern?.id) {
			window.location.href = `/patterns/story/${pattern.id}`;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Pattern</h1>
	</div>

	{#if loading}
		<div class="message">Loading pattern...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if pattern}
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
									id="pattern-name"
									type="text"
									bind:value={pattern.name}
									class="input__text"
									class:input__text_changed={pattern.name?.length > 0}
									required
								/>
								<label for="pattern-name" class="input__label">Name</label>
							</div>

							<div class="input">
								<input
									id="pattern-description"
									type="text"
									bind:value={pattern.description}
									class="input__text"
									class:input__text_changed={pattern.description?.length > 0}
									required
								/>
								<label for="pattern-description" class="input__label">Description</label>
							</div>
						</div>

						<div class="form-section">
							<h3>Classification</h3>
							<div class="input input_select">
								<select
									id="pattern-kind"
									bind:value={pattern.kind}
									class="input__text input__text_changed"
									required
								>
									{#each kinds as k}
										<option value={k}>{k}</option>
									{/each}
								</select>
								<label for="pattern-kind" class="input__label">Kind</label>
							</div>

							<div class="input input_select">
								<select
									id="pattern-taxonomy"
									bind:value={pattern.taxonomy}
									class="input__text"
									class:input__text_changed={pattern.taxonomy}
								>
									{#each taxonomyOptions as t}
										<option value={t}>{t || 'Select Taxonomy (Optional)'}</option>
									{/each}
								</select>
								<label for="pattern-taxonomy" class="input__label">Taxonomy</label>
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
							{#if pattern.story_md}
								<button
									type="button"
									class="button button_secondary"
									onclick={goToStoryEditor}
									disabled={isSaving}
								>
									Edit Story
								</button>
							{/if}
							<button type="submit" class="button button_green" disabled={isSaving}>
								{isSaving ? 'Saving...' : 'Save'}
							</button>
						</div>
					</form>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Pattern not found</div>
	{/if}
</div>
