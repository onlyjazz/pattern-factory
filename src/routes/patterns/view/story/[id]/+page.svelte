<script lang="ts">
	import { page } from '$app/stores';
	import { marked } from 'marked';

	let entity: any = null;
	let loading = true;
	let error: string | null = null;

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
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load pattern';
			entity = null;
		} finally {
			loading = false;
		}
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">{entity?.name || 'Pattern Story'}</h1>
	</div>

	{#if loading}
		<div class="message">Loading...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if entity}
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="entity-card">
					<div class="story-view-content">
						{@html marked(entity.story_md || '')}
					</div>
				</div>
			</div>
		</div>
	{:else}
		<div class="message">Not found</div>
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
		margin: 10px 0 10px 20px;
	}

	.story-view-content :global(li) {
		margin: 5px 0;
	}
</style>
