<script lang="ts">
	import { onMount } from 'svelte';
	import marked from 'marked';

	interface Card {
		id: string;
		name: string;
		description: string;
	}

	let card: Card | null = null;
	let storyContent = '';
	let loading = true;
	let error: string | null = null;
	let saving = false;
	let saveError: string | null = null;

	export let data: any;

	onMount(async () => {
		try {
			const id = data.id;
			const response = await fetch(`/api/cards/${id}`);

			if (!response.ok) {
				throw new Error(`Failed to load card: ${response.statusText}`);
			}

			card = await response.json();
			storyContent = card.description || '';
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function getRenderedMarkdown(markdown: string): string {
		if (!markdown) return '';
		return marked.parse(markdown);
	}

	async function saveStory() {
		if (!card?.id) return;

		saving = true;
		saveError = null;

		try {
			const response = await fetch(`/api/cards/${card.id}`, {
				method: 'PATCH',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					description: storyContent
				})
			});

			if (!response.ok) {
				throw new Error(`Failed to save card: ${response.statusText}`);
			}

			const updatedCard = await response.json();
			card = updatedCard;

			// Navigate back to patterns after save
			window.location.href = `/cards`;
		} catch (err) {
			saveError = err instanceof Error ? err.message : 'Unknown error';
		} finally {
			saving = false;
		}
	}

	function cancel() {
		window.history.back();
	}
</script>

<div class="story-editor-wrapper">
	{#if loading}
		<div class="loading">Loading...</div>
	{:else if error}
		<div class="error">{error}</div>
	{:else if card}
		<div class="story-editor-container">
			<div class="story-editor-editor">
				<label class="editor-label">Edit Story</label>
				<textarea
					class="story-editor-textarea"
					bind:value={storyContent}
					placeholder="Enter markdown here..."
				></textarea>
			</div>

			<div class="story-editor-preview">
				<label class="preview-label">Preview</label>
				<div class="story-editor-preview-content">
					{@html getRenderedMarkdown(storyContent)}
				</div>
			</div>
		</div>

		{#if saveError}
			<div class="error" style="margin-top: 1rem;">
				{saveError}
			</div>
		{/if}

		<div class="button-group">
			<button class="cancel-btn" on:click={cancel} disabled={saving}>Cancel</button>
			<button class="save-btn" on:click={saveStory} disabled={saving}>
				{saving ? 'Saving...' : 'Save'}
			</button>
		</div>
	{:else}
		<div class="error">Card not found</div>
	{/if}
</div>

<style>
	.story-editor-wrapper {
		padding: 2rem;
		max-width: 1200px;
		margin: 0 auto;
	}

	.loading,
	.error {
		padding: 1rem;
		text-align: center;
		font-size: 1rem;
	}

	.error {
		color: #d32f2f;
	}

	.button-group {
		display: flex;
		gap: 1rem;
		margin-top: 1.5rem;
		justify-content: flex-start;
	}

	.cancel-btn,
	.save-btn {
		padding: 0.75rem 1.5rem;
		border: none;
		border-radius: 4px;
		font-size: 1rem;
		cursor: pointer;
		font-weight: 500;
		transition: background-color 0.2s;
	}

	.cancel-btn {
		background-color: #f44336;
		color: white;
	}

	.cancel-btn:hover:not(:disabled) {
		background-color: #d32f2f;
	}

	.save-btn {
		background-color: #4caf50;
		color: white;
	}

	.save-btn:hover:not(:disabled) {
		background-color: #45a049;
	}

	.cancel-btn:disabled,
	.save-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
</style>
