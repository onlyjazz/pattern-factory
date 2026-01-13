<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { Card } from '$lib/db';
	import { marked } from 'marked';

	let card: Card | null = null;
	let loading = true;
	let error: string | null = null;
	let saving = false;

	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const cardId = $page.params.id;
			const response = await fetch(`${apiBase}/cards/${cardId}`);
			if (!response.ok) throw new Error('Failed to fetch card');
			const data = await response.json();
			card = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	async function handleSave() {
		if (!card) return;
		try {
			saving = true;
			const response = await fetch(`${apiBase}/cards/${card.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					markdown: card.markdown || null
				})
			});
			if (!response.ok) throw new Error('Failed to save card');
			error = null;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save card';
		} finally {
			saving = false;
		}
	}

	function goBack() {
		window.history.back();
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<button class="button button_secondary" onclick={goBack}>
			← Back
		</button>
		<h1 class="heading heading_1">Edit Card Markdown</h1>
	</div>

	<div class="grid-row">
		<div class="grid-col grid-col_24">
			{#if loading}
				<div class="message">Loading card...</div>
			{:else if error}
				<div class="message message-error">Error: {error}</div>
			{:else if card}
				<div class="editor-container">
					<div class="editor-section">
						<div class="section-title">Card Name</div>
						<div class="card-name">{card.name}</div>
					</div>

					<div class="editor-section">
						<div class="section-title">Card Description</div>
						<div class="card-description">{card.description}</div>
					</div>

					<div class="editor-grid">
						<div class="editor-pane">
							<div class="pane-header">
								<span class="pane-title">Markdown Editor</span>
								<button
									class="button button_green"
									onclick={handleSave}
									disabled={saving}
								>
									{saving ? 'Saving...' : 'Save'}
								</button>
							</div>
							<textarea
								bind:value={card.markdown}
								class="editor-textarea"
								placeholder="Enter markdown content for this card..."
							></textarea>
						</div>

						<div class="preview-pane">
							<div class="pane-header">
								<span class="pane-title">Preview</span>
							</div>
							<div class="preview-content">
								{@html marked(card.markdown || '')}
							</div>
						</div>
					</div>
				</div>
			{:else}
				<div class="message">Card not found</div>
			{/if}
		</div>
	</div>
</div>

<style>
	#application-content-area {
		padding: 2rem;
	}

	.page-title {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 2rem;
	}

	.page-title h1 {
		margin: 0;
		flex: 1;
	}

	.editor-container {
		display: flex;
		flex-direction: column;
		gap: 2rem;
	}

	.editor-section {
		background: white;
		padding: 1.5rem;
		border-radius: 8px;
		border: 1px solid #ddd;
	}

	.section-title {
		font-size: 12px;
		font-weight: 600;
		text-transform: uppercase;
		color: #666;
		margin-bottom: 0.5rem;
		letter-spacing: 0.05em;
	}

	.card-name {
		font-size: 24px;
		font-weight: bold;
		color: #333;
	}

	.card-description {
		font-size: 16px;
		color: #555;
		line-height: 1.5;
	}

	.editor-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 1.5rem;
		min-height: 600px;
	}

	.editor-pane,
	.preview-pane {
		display: flex;
		flex-direction: column;
		background: white;
		border: 1px solid #ddd;
		border-radius: 8px;
		overflow: hidden;
	}

	.pane-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1rem;
		border-bottom: 1px solid #ddd;
		background: #f9f9f9;
	}

	.pane-title {
		font-weight: 600;
		color: #333;
		font-size: 14px;
	}

	.editor-textarea {
		flex: 1;
		padding: 1rem;
		border: none;
		font-family: 'Monaco', 'Courier New', monospace;
		font-size: 14px;
		line-height: 1.6;
		resize: none;
		color: #333;
	}

	.editor-textarea:focus {
		outline: none;
		background-color: #fafafa;
	}

	.preview-content {
		flex: 1;
		padding: 1rem;
		overflow-y: auto;
		font-size: 14px;
		line-height: 1.6;
		color: #333;
	}

	/* Markdown rendering styles */
	:global(.preview-content h1) {
		font-size: 28px;
		font-weight: bold;
		margin: 1.5rem 0 1rem 0;
		color: #222;
	}

	:global(.preview-content h2) {
		font-size: 24px;
		font-weight: bold;
		margin: 1.3rem 0 0.8rem 0;
		color: #333;
		border-bottom: 1px solid #eee;
		padding-bottom: 0.3rem;
	}

	:global(.preview-content h3) {
		font-size: 20px;
		font-weight: bold;
		margin: 1.1rem 0 0.6rem 0;
		color: #444;
	}

	:global(.preview-content p) {
		margin: 0.8rem 0;
	}

	:global(.preview-content ul),
	:global(.preview-content ol) {
		margin: 0.8rem 0 0.8rem 1.5rem;
	}

	:global(.preview-content li) {
		margin: 0.4rem 0;
	}

	:global(.preview-content code) {
		background: #f4f4f4;
		padding: 2px 6px;
		border-radius: 3px;
		font-family: 'Monaco', 'Courier New', monospace;
		font-size: 13px;
		color: #d63384;
	}

	:global(.preview-content pre) {
		background: #f4f4f4;
		padding: 1rem;
		border-radius: 4px;
		overflow-x: auto;
		margin: 0.8rem 0;
	}

	:global(.preview-content pre code) {
		background: none;
		padding: 0;
		color: #333;
	}

	:global(.preview-content blockquote) {
		border-left: 4px solid #ddd;
		padding-left: 1rem;
		margin: 0.8rem 0;
		color: #666;
		font-style: italic;
	}

	:global(.preview-content a) {
		color: #0066cc;
		text-decoration: none;
	}

	:global(.preview-content a:hover) {
		text-decoration: underline;
	}

	:global(.preview-content hr) {
		border: none;
		border-top: 1px solid #ddd;
		margin: 1.5rem 0;
	}

	:global(.preview-content table) {
		border-collapse: collapse;
		width: 100%;
		margin: 0.8rem 0;
	}

	:global(.preview-content th),
	:global(.preview-content td) {
		border: 1px solid #ddd;
		padding: 0.6rem;
		text-align: left;
	}

	:global(.preview-content th) {
		background: #f4f4f4;
		font-weight: bold;
	}

	.message {
		padding: 2rem;
		text-align: center;
		font-size: 16px;
		color: #666;
		background: white;
		border-radius: 8px;
		border: 1px solid #ddd;
	}

	.message-error {
		color: #d32f2f;
		background: #ffebee;
		border-color: #ffcdd2;
	}

	@media (max-width: 1200px) {
		.editor-grid {
			grid-template-columns: 1fr;
			min-height: auto;
		}
	}
</style>
