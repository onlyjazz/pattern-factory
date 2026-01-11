<script lang="ts">
	import { page } from '$app/stores';
	import type { Pattern } from '$lib/db';
	import { marked } from 'marked';

	let pattern: Pattern | null = null;
	let loading = true;
	let error: string | null = null;
	let showStoryEditor = false;
	let patternToEdit: Pattern | null = null;

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

	function openStoryEditor() {
		if (pattern) {
			patternToEdit = { ...pattern };
			showStoryEditor = true;
		}
	}

	function closeStoryEditor() {
		showStoryEditor = false;
		patternToEdit = null;
	}

	async function handleSaveStory() {
		if (!patternToEdit) return;
		try {
			const response = await fetch(`${apiBase}/patterns/${patternToEdit.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					story_md: patternToEdit.story_md || null
				})
			});
			if (!response.ok) throw new Error('Failed to save story');
			const updated = await response.json();
			pattern = { ...updated, id: String(updated.id) };
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
					<div class="message">Pattern not found</div>
					<a href="/patterns" class="button button_secondary">Back to Patterns</a>
				</div>
			</div>
		</div>
	{/if}
</div>

<!-- STORY EDITOR MODAL -->
{#if showStoryEditor && patternToEdit}
	<div class="modal-overlay" onclick={closeStoryEditor}>
		<div class="story-editor-content" role="dialog" aria-labelledby="story-editor-title" onclick={(e) => e.stopPropagation()}>
			<div class="modal-header">
				<h2 id="story-editor-title" class="heading heading_2">Edit Story: {patternToEdit.name}</h2>
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
						bind:value={patternToEdit.story_md}
						class="story-editor-textarea"
						placeholder="Enter your story in Markdown format..."
					></textarea>
				</div>
				<div class="story-editor-preview">
					<div class="preview-label">Preview</div>
					<div class="story-editor-preview-content">
						{@html marked(patternToEdit.story_md || '')}
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

	:global(.modal-overlay) {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
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

	:global(.modal-header) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 20px;
		border-bottom: 1px solid #eee;
	}

	:global(.modal-close) {
		background: none;
		border: none;
		font-size: 24px;
		cursor: pointer;
		color: #666;
		padding: 0;
		width: 30px;
		height: 30px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	:global(.modal-close:hover) {
		color: #333;
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

	:global(.story-editor-textarea:focus) {
		outline: none;
		border-color: #999;
	}

	:global(.story-editor-preview) {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
		border: 1px solid #ddd;
		border-radius: 4px;
		background: #f9f9f9;
	}

	:global(.preview-label) {
		padding: 8px 10px;
		font-size: 12px;
		font-weight: bold;
		color: #666;
		border-bottom: 1px solid #ddd;
		background: #f0f0f0;
	}

	:global(.story-editor-preview-content) {
		flex: 1;
		overflow-y: auto;
		padding: 10px;
		font-size: 14px;
		line-height: 1.5;
	}

	:global(.story-editor-preview-content h1) {
		font-size: 24px;
		font-weight: bold;
		margin: 15px 0 10px 0;
	}

	:global(.story-editor-preview-content h2) {
		font-size: 20px;
		font-weight: bold;
		margin: 12px 0 8px 0;
	}

	:global(.story-editor-preview-content h3) {
		font-size: 16px;
		font-weight: bold;
		margin: 10px 0 6px 0;
	}

	:global(.story-editor-preview-content p) {
		margin: 8px 0;
	}

	:global(.story-editor-preview-content ul),
	:global(.story-editor-preview-content ol) {
		margin: 8px 0 8px 20px;
	}

	:global(.story-editor-preview-content li) {
		margin: 4px 0;
	}

	:global(.story-editor-preview-content code) {
		background: #e0e0e0;
		padding: 2px 6px;
		border-radius: 3px;
		font-family: 'Monaco', 'Courier New', monospace;
		font-size: 12px;
	}

	:global(.story-editor-preview-content blockquote) {
		border-left: 4px solid #ccc;
		padding-left: 10px;
		margin: 8px 0;
		color: #666;
		font-style: italic;
	}

	:global(.modal-footer) {
		display: flex;
		gap: 10px;
		justify-content: flex-end;
		margin-top: 20px;
		padding: 15px 20px;
		border-top: 1px solid #eee;
	}
</style>
