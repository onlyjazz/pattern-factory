<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { Card, Pattern } from '$lib/db';

	let card: Card | null = null;
	let patterns: Pattern[] = [];
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

	let patternSearchQuery = '';
	let filteredPatterns: Pattern[] = [];
	let showPatternDropdown = false;
	let selectedPatternId: number | null = null;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const cardId = $page.params.id;
			
			// Load card
			const cardResponse = await fetch(`${apiBase}/cards/${cardId}`);
			if (!cardResponse.ok) throw new Error('Failed to fetch card');
			const cardData = await cardResponse.json();
			card = { ...cardData, id: String(cardData.id) };
			
			// Load patterns
			const patternsResponse = await fetch(`${apiBase}/patterns`);
			if (!patternsResponse.ok) throw new Error('Failed to fetch patterns');
			patterns = await patternsResponse.json();
			
			if (card.pattern_id) {
				selectedPatternId = card.pattern_id;
				const selectedPattern = patterns.find(p => p.id === card.pattern_id);
				if (selectedPattern) {
					patternSearchQuery = selectedPattern.name;
				}
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function searchPatterns(query: string) {
		if (!query.trim()) {
			filteredPatterns = [];
			showPatternDropdown = false;
			return;
		}
		
		filteredPatterns = patterns.filter(p =>
			p.name.toLowerCase().includes(query.toLowerCase()) ||
			p.description.toLowerCase().includes(query.toLowerCase())
		);
		showPatternDropdown = true;
	}

	function selectPattern(pattern: Pattern) {
		selectedPatternId = pattern.id as any;
		patternSearchQuery = pattern.name;
		filteredPatterns = [];
		showPatternDropdown = false;
		if (card) {
			card.pattern_id = pattern.id as any;
		}
	}

	async function handleSave() {
		if (!card) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/cards/${card.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: card.name,
					description: card.description,
					pattern_id: selectedPatternId,
					story: card.story || null,
					order_index: card.order_index || 0,
					domain: card.domain || null,
					audience: card.audience || null,
					maturity: card.maturity || null
				})
			});
			if (!response.ok) throw new Error('Failed to save card');
			// Navigate back to view page
			window.location.href = `/cards/view/${card.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save card';
			isSaving = false;
		}
	}

	function handleCancel() {
		if (card?.id) {
			window.location.href = `/cards/view/${card.id}`;
		}
	}

	function goToStoryEditor() {
		if (card?.id) {
			window.location.href = `/cards/edit/story/${card.id}`;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Card</h1>
	</div>

	{#if loading}
		<div class="message">Loading card...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if card}
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
									id="card-name"
									type="text"
									bind:value={card.name}
									class="input__text"
									class:input__text_changed={card.name?.length > 0}
									required
								/>
								<label for="card-name" class="input__label">Name</label>
							</div>

							<div class="input">
								<input
									id="card-description"
									type="text"
									bind:value={card.description}
									class="input__text"
									class:input__text_changed={card.description?.length > 0}
									required
								/>
								<label for="card-description" class="input__label">Description</label>
							</div>
						</div>

						<div class="form-section">
							<h3>Pattern</h3>
							<div class="input input_select">
								<div class="pattern-search-container">
									<input
										id="card-pattern-search"
										type="text"
										bind:value={patternSearchQuery}
										oninput={(e) => searchPatterns((e.target as HTMLInputElement).value)}
										class="input__text input__text_changed"
										placeholder="Search patterns..."
										required
									/>
									<label for="card-pattern-search" class="input__label">Pattern</label>
									{#if showPatternDropdown && filteredPatterns.length > 0}
										<div class="pattern-dropdown">
											{#each filteredPatterns as pattern}
												<div class="pattern-option" onclick={() => selectPattern(pattern)}>
													<div class="pattern-name">{pattern.name}</div>
													<div class="pattern-description">{pattern.description}</div>
												</div>
											{/each}
										</div>
									{/if}
								</div>
							</div>
						</div>

						<div class="form-section">
							<h3>Details</h3>
							<div class="input">
								<input
									id="card-order-index"
									type="number"
									bind:value={card.order_index}
									class="input__text"
									class:input__text_changed={card.order_index}
								/>
								<label for="card-order-index" class="input__label">Order Index</label>
							</div>

							<div class="input">
								<input
									id="card-domain"
									type="text"
									bind:value={card.domain}
									class="input__text"
									class:input__text_changed={card.domain?.length > 0}
								/>
								<label for="card-domain" class="input__label">Domain</label>
							</div>

							<div class="input">
								<input
									id="card-audience"
									type="text"
									bind:value={card.audience}
									class="input__text"
									class:input__text_changed={card.audience?.length > 0}
								/>
								<label for="card-audience" class="input__label">Audience</label>
							</div>

							<div class="input">
								<input
									id="card-maturity"
									type="text"
									bind:value={card.maturity}
									class="input__text"
									class:input__text_changed={card.maturity?.length > 0}
								/>
								<label for="card-maturity" class="input__label">Maturity</label>
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
							<button
								type="button"
								class="button button_secondary"
								onclick={goToStoryEditor}
								disabled={isSaving}
							>
								Edit Story
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
		<div class="message">Card not found</div>
	{/if}
</div>

<style>
	.pattern-search-container {
		position: relative;
	}

	.pattern-dropdown {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		background: white;
		border: 1px solid #ddd;
		border-top: none;
		border-radius: 0 0 4px 4px;
		max-height: 200px;
		overflow-y: auto;
		z-index: 10;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
	}

	.pattern-option {
		padding: 10px 12px;
		cursor: pointer;
		border-bottom: 1px solid #f0f0f0;
	}

	.pattern-option:hover {
		background-color: #f5f5f5;
	}

	.pattern-name {
		font-weight: 500;
		color: #333;
		font-size: 14px;
	}

	.pattern-description {
		font-size: 12px;
		color: #666;
		margin-top: 4px;
	}
</style>
