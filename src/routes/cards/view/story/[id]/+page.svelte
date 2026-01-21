<script lang="ts">
	import { onMount } from 'svelte';
	import { marked } from 'marked';

		interface Card {
			id: string;
			name: string;
			story: string;
		}

	let card: Card | null = null;
	let loading = true;
	let error: string | null = null;

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
</script>

<div class="story-view-container">
	{#if loading}
		<div class="loading">Loading...</div>
	{:else if error}
		<div class="error">{error}</div>
	{:else if card}
		<div class="story-view-content">
			<h1>{card.name}</h1>
			<div class="story-text">
				{@html getRenderedMarkdown(card.story || '')}
			</div>
		</div>
	{:else}
		<div class="error">Card not found</div>
	{/if}
</div>

<style>
	.story-view-container {
		padding: 2rem;
		max-width: 900px;
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

	.story-view-content {
		background: white;
		border: 1px solid #e0e0e0;
		border-radius: 4px;
		padding: 2rem;
	}

	.story-view-content h1 {
		margin-top: 0;
		margin-bottom: 1.5rem;
		font-size: 2rem;
		color: #1a1a1a;
	}

	.story-text {
		line-height: 1.6;
		color: #333;
	}

	.story-text :global(h1) {
		font-size: 1.75rem;
		margin-top: 1.5rem;
		margin-bottom: 0.75rem;
		border-bottom: 2px solid #ddd;
		padding-bottom: 0.5rem;
	}

	.story-text :global(h2) {
		font-size: 1.5rem;
		margin-top: 1.25rem;
		margin-bottom: 0.5rem;
		color: #2c3e50;
	}

	.story-text :global(h3) {
		font-size: 1.25rem;
		margin-top: 1rem;
		margin-bottom: 0.5rem;
		color: #34495e;
	}

	.story-text :global(p) {
		margin: 0.75rem 0;
	}

	.story-text :global(ul),
	.story-text :global(ol) {
		margin: 0.75rem 0;
		padding-left: 2rem;
	}

	.story-text :global(li) {
		margin: 0.25rem 0;
	}

	.story-text :global(blockquote) {
		border-left: 4px solid #ddd;
		margin: 1rem 0;
		padding-left: 1rem;
		color: #666;
		font-style: italic;
	}

	.story-text :global(code) {
		background: #f5f5f5;
		padding: 0.2rem 0.4rem;
		border-radius: 3px;
		font-family: 'Courier New', monospace;
		font-size: 0.9em;
	}

	.story-text :global(pre) {
		background: #f5f5f5;
		border: 1px solid #ddd;
		border-radius: 4px;
		padding: 1rem;
		overflow-x: auto;
		margin: 1rem 0;
	}

	.story-text :global(pre code) {
		background: transparent;
		padding: 0;
	}

	.story-text :global(a) {
		color: #1976d2;
		text-decoration: none;
	}

	.story-text :global(a:hover) {
		text-decoration: underline;
	}

	.story-text :global(table) {
		border-collapse: collapse;
		width: 100%;
		margin: 1rem 0;
	}

	.story-text :global(th),
	.story-text :global(td) {
		border: 1px solid #ddd;
		padding: 0.75rem;
		text-align: left;
	}

	.story-text :global(th) {
		background: #f5f5f5;
		font-weight: bold;
	}
</style>
