<script lang="ts">
	export let loading = false;
	export let error: string | null = null;
	export let isEditing = false;
	export let entityName = 'Entity';
	export let pageTitle = 'Entity';
	export let entity: any = null;
	export let saveError: string | null = null;
	export let isSaving = false;
	export let onEdit: (() => void) | null = null;
	export let onCancel: (() => void) | null = null;
	export let onSave: ((e: Event) => void) | null = null;
</script>

<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">{pageTitle}</h1>
	</div>

	{#if loading}
		<div class="message">Loading {entityName.toLowerCase()}...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if entity}
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="entity-card">
					{#if saveError}
						<div class="message message-error" style="margin-bottom: 20px;">Error: {saveError}</div>
					{/if}

					{#if isEditing}
						<div class="entity-view-header">
							<h2 class="heading heading_3">{entity.name}</h2>
							<div style="display: flex; gap: 10px;">
								<button
									type="button"
									class="button button_secondary"
									onclick={onCancel}
									disabled={isSaving}
								>
									Cancel
								</button>
								<button type="submit" class="button button_green" onclick={onSave} disabled={isSaving}>
									{isSaving ? 'Saving...' : 'Save'}
								</button>
							</div>
						</div>
						<form onsubmit={(e) => {e.preventDefault(); onSave?.(e);}}>
							<slot name="content" />
						</form>
					{:else}
						<div class="entity-view-header">
							<h2 class="heading heading_3">{entity.name}</h2>
							<button class="button button_green" onclick={onEdit}>
								EDIT
							</button>
						</div>
						<slot name="content" />
					{/if}
				</div>
			</div>
		</div>
	{:else}
		<div class="message">{entityName} not found</div>
	{/if}
</div>
