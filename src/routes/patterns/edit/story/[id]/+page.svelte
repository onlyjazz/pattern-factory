<script lang="ts">
	import { page } from '$app/stores';
	import { marked } from 'marked';

	let entity: any = null;
	let storyContent = '';
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;

	const apiBase = 'http://localhost:8000';

	$: if ($page.params.id) {
		loadEntity($page.params.id);
	}

	async function loadEntity(id: string) {
		try {
			loading = true;
			error = null;
			const response = await fetch(`${apiBase}/patterns/${id}`);
			if (!response.ok) throw new Error('Pattern not found');
			const data = await response.json();
			entity = { ...data, id: String(data.id) };
			storyContent = entity.story_md || '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load pattern';
			entity = null;
		} finally {
			loading = false;
		}
	}

	async function handleSave() {
		if (!entity) return;
		try {
			isSaving = true;
			saveError = null;
			const response = await fetch(`${apiBase}/patterns/${entity.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					story_md: storyContent
				})
			});
			if (!response.ok) throw new Error('Failed to save story');
			// Navigate back to edit page
			window.location.href = `/patterns/${entity.id}/edit`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save story';
			isSaving = false;
		}
	}

	function handleCancel() {
		// Navigate back to edit page
		window.location.href = `/patterns/${entity?.id}/edit`;
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Pattern Story</h1>
	</div>

	{#if loading}
		<div class="message">Loading...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if entity}
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
		<div class="message">Not found</div>
	{/if}
</div>
