<script lang="ts">
	import { page } from '$app/stores';
	import type { Card } from '$lib/db';
	import { marked } from 'marked';

	let card: Card | null = null;
	let loading = true;
	let error: string | null = null;
	let showStoryEditor = false;
	let cardToEdit: Card | null = null;

	const apiBase = 'http://localhost:8000';

	$: if ($page.params.id) {
		loadCard($page.params.id);
	}

	async function loadCard(id: string) {
		try {
			loading = true;
			error = null;
			const response = await fetch(`${apiBase}/cards/${id}`);
			if (!response.ok) throw new Error('Card not found');
			const data = await response.json();
			card = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load card';
			card = null;
		} finally {
			loading = false;
		}
	}

	function openStoryEditor() {
		if (card) {
			cardToEdit = { ...card };
			showStoryEditor = true;
		}
	}

	function closeStoryEditor() {
		showStoryEditor = false;
		cardToEdit = null;
	}

	async function handleSaveStory() {
		if (!cardToEdit) return;
		try {
			const response = await fetch(`${apiBase}/cards/${cardToEdit.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					markdown: cardToEdit.markdown || null
				})
			});
			if (!response.ok) throw new Error('Failed to save story');
			const updated = await response.json();
			card = { ...updated, id: String(updated.id) };
			closeStoryEditor();
		} catch (e) {
			console.error('Failed to save story:', e);
		}
	}
</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	{#if loading}
		<div class="page-title">
			<h1 class="heading heading_1">Loading...</h1>
		</div>
	{:else if error}
		<div class="page-title">
			<h1 class="heading heading_1">Error</h1>
		</div>
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="studies card">
					<div class="message message-error">{error}</div>
					<a href="/cards" class="button button_secondary">Back to Cards</a>
				</div>
			</div>
		</div>
	{:else if card}
		<div class="page-title">
			<h1 class="heading heading_1">{card.name}</h1>
		</div>

		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="studies card">
					<div class="story-view-content">
						{@html marked(card.markdown || '')}
					</div>
					<div class="story-view-footer">
						<a href="/cards/view/{card.id}" class="button button_secondary">Back to Card</a>
						<button onclick={openStoryEditor} class="button button_secondary">Edit</button>
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="page-title">
			<h1 class="heading heading_1">Not Found</h1>
		</div>
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="studies card">
					<div class="message">Card not found</div>
					<a href="/cards" class="button button_secondary">Back to Cards</a>
				</div>
			</div>
		</div>
	{/if}
</div>

<!-- STORY EDITOR MODAL -->
{#if showStoryEditor && cardToEdit}
	<div class="modal-overlay" onclick={closeStoryEditor}>
		<div class="story-editor-content" role="dialog" aria-labelledby="story-editor-title" onclick={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2 id="story-editor-title" class="heading heading_2">Edit Story: {cardToEdit.name}</h2>
				<button
					class="modal-close"
					onclick={closeStoryEditor}
					title="Close"
				>
					×
				</button>
			</div>

			<div class="story-editor-body">
				<div class="story-editor-editor">
					<textarea
						id="story-editor-textarea"
						bind:value={cardToEdit.markdown}
						class="story-editor-textarea"
						placeholder="Enter your story in Markdown format..."
					></textarea>
				</div>
				<div class="story-editor-preview">
					<div class="preview-label">Preview</div>
					<div class="story-editor-preview-content">
						{@html marked(cardToEdit.markdown || '')}
					</div>
				</div>
			</div>

			<div class="modal-footer">
				<button
					type="button"
					class="button button_secondary"
					onclick={closeStoryEditor}
				>
					Cancel
				</button>
				<button
					type="button"
					class="button button_green"
					onclick={handleSaveStory}
				>
					Save
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.story-view-content {
		padding: 20px;
		font-size: 15px;
		line-height: 1.7;
		color: #495057;
	}

	.story-view-content :global(h1) {
		font-size: 24px;
		font-weight: 600;
		margin: 20px 0 12px 0;
	}

	.story-view-content :global(h2) {
		font-size: 20px;
		font-weight: 600;
		margin: 16px 0 10px 0;
	}

	.story-view-content :global(h3) {
		font-size: 16px;
		font-weight: 600;
		margin: 12px 0 8px 0;
	}

	.story-view-content :global(p) {
		margin: 10px 0;
	}

	.story-view-content :global(ul),
	.story-view-content :global(ol) {
		margin: 10px 0 10px 20px;
	}

	.story-view-content :global(li) {
		margin: 5px 0;
	}

	.story-view-footer {
		display: flex;
		gap: 10px;
		justify-content: flex-start;
		padding: 0 20px 20px;
	}

	:global(.story-editor-content) {
		background: white;
		border-radius: 8px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		max-width: 1000px;
		width: 90%;
		max-height: 85vh;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	:global(.story-editor-body) {
		display: flex;
		gap: 15px;
		padding: 20px;
		flex: 1;
		min-height: 0;
	}

	:global(.story-editor-editor) {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	:global(.story-editor-textarea) {
		flex: 1;
		padding: 10px;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-family: 'Monaco', 'Courier New', monospace;
		font-size: 14px;
		resize: none;
		width: 100%;
	}

	:global(.story-editor-preview) {
		flex: 0 0 45%;
		display: flex;
		flex-direction: column;
		border: 1px solid #ddd;
		border-radius: 4px;
		background: #fafafa;
		overflow: hidden;
	}

	:global(.preview-label) {
		padding: 10px;
		font-weight: 600;
		font-size: 14px;
		border-bottom: 1px solid #ddd;
		background: #f0f0f0;
	}

	:global(.story-editor-preview-content) {
		flex: 1;
		overflow-y: auto;
		padding: 15px;
		font-size: 14px;
		line-height: 1.5;
	}

	:global(.story-editor-preview-content h1),
	:global(.story-editor-preview-content h2),
	:global(.story-editor-preview-content h3) {
		margin-top: 0;
	}
</style>
