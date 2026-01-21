<script lang="ts">
	import { page } from '$app/stores';
	import type { Card } from '$lib/db';
	import { marked } from 'marked';

	let card: Card | null = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

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

	async function handleSave() {
		if (!card) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/cards/${card.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					markdown: card.markdown || null
				})
			});
			if (!response.ok) throw new Error('Failed to save story');
			window.location.href = `/cards/story/${card.id}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save story';
			isSaving = false;
		}
	}

	function handleCancel() {
		window.location.href = `/cards/view/${card?.id}`;
	}
</script>
			console.error('Failed to save story:', e);
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Card Story</h1>
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

					<div class="story-editor-container">
						<div class="story-editor-editor">
							<label class="editor-label">Story (Markdown)</label>
							<textarea
								id="story-editor-textarea"
								bind:value={card.markdown}
								class="story-editor-textarea"
								placeholder="Enter your story in Markdown format..."
							></textarea>
						</div>
						<div class="story-editor-preview">
							<label class="preview-label">Preview</label>
							<div class="story-editor-preview-content">
								{@html marked(card.markdown || '')}
							</div>
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
							class="button button_green"
							onclick={handleSave}
							disabled={isSaving}
						>
							{isSaving ? 'Saving...' : 'Save'}
						</button>
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Card not found</div>
	{/if}
</div>

