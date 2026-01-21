<script lang="ts">
	import { onMount } from 'svelte';
	import { marked } from 'marked';

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

	const apiBase = 'http://localhost:8000';

	export let data: any;

	onMount(async () => {
		try {
			const id = data.id;
			const response = await fetch(`${apiBase}/cards/${id}`);

			if (!response.ok) {
				throw new Error(`Failed to load card: ${response.statusText}`);
			}

			card = await response.json();
			storyContent = card.story || '';
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
			const response = await fetch(`${apiBase}/cards/${card.id}`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					story: storyContent
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

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Card Story</h1>
	</div>

	{#if loading}
		<div class="message">Loading...</div>
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
								bind:value={storyContent}
								class="story-editor-textarea"
								placeholder="Enter your story in Markdown format..."
							></textarea>
						</div>
						<div class="story-editor-preview">
							<label class="preview-label">Preview</label>
							<div class="story-editor-preview-content">
								{@html marked(storyContent)}
							</div>
						</div>
					</div>

					<div class="form-footer">
						<button
							type="button"
							class="button button_secondary"
							onclick={cancel}
							disabled={saving}
						>
							Cancel
						</button>
						<button
							type="button"
							class="button button_green"
							onclick={saveStory}
							disabled={saving}
						>
							{saving ? 'Saving...' : 'Save'}
						</button>
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Not found</div>
	{/if}
</div>

