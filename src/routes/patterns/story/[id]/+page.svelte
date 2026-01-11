<script lang="ts">
	import { page } from '$app/stores';
	import type { Pattern } from '$lib/db';
	import { marked } from 'marked';

	let pattern: Pattern | null = null;
	let loading = true;
	let error: string | null = null;

	const apiBase = 'http://localhost:8000';

	$: if ($page.params.id) {
		loadPattern($page.params.id);
	}

	async function loadPattern(id: string) {
		try {
			loading = true;
			error = null;
			const response = await fetch(`${apiBase}/patterns/${id}`);
			if (!response.ok) throw new Error('Pattern not found');
			const data = await response.json();
			pattern = { ...data, id: String(data.id) };
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load pattern';
			pattern = null;
		} finally {
			loading = false;
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
					<a href="/patterns" class="button button_secondary">Back to Patterns</a>
				</div>
			</div>
		</div>
	{:else if pattern}
		<div class="page-title">
			<h1 class="heading heading_1">{pattern.name}</h1>
		</div>

		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="studies card">
					<div class="story-view-content">
						{@html marked(pattern.story_md || '')}
					</div>
					<div class="story-view-footer">
						<a href="/patterns" class="button button_secondary">Back to Patterns</a>
						<a href="/patterns" class="button button_secondary">Edit</a>
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
					<div class="message">Pattern not found</div>
					<a href="/patterns" class="button button_secondary">Back to Patterns</a>
				</div>
			</div>
		</div>
	{/if}
</div>

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
		margin: 10px 0 10px 25px;
	}

	.story-view-content :global(li) {
		margin: 5px 0;
	}

	.story-view-content :global(code) {
		background: #f0f0f0;
		padding: 2px 6px;
		border-radius: 3px;
		font-family: 'Monaco', 'Courier New', monospace;
		font-size: 13px;
		color: #d63384;
	}

	.story-view-content :global(pre) {
		background: #f5f5f5;
		padding: 12px;
		border-radius: 4px;
		overflow-x: auto;
		margin: 10px 0;
		font-size: 13px;
	}

	.story-view-content :global(blockquote) {
		border-left: 4px solid #dee2e6;
		padding-left: 15px;
		margin: 12px 0;
		color: #6c757d;
		font-style: italic;
	}

	.story-view-content :global(strong) {
		font-weight: 600;
	}

	.story-view-content :global(em) {
		font-style: italic;
	}

	.story-view-footer {
		display: flex;
		gap: 10px;
		justify-content: flex-end;
		padding: 15px 20px;
		border-top: 1px solid #dee2e6;
		background-color: #f8f9fa;
	}
</style>
