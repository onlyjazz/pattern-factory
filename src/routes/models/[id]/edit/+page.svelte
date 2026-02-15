<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import type { Model } from '$lib/db';
	import CheckboxField from '$lib/CheckboxField.svelte';
	
	let model: Partial<Model> = {};
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isSaving = false;
	let duplicateModel = false;
	
	const apiBase = 'http://localhost:8000';
	
	onMount(async () => {
		// Get model ID from route params
		const modelId = $page.params.id;
		
		try {
			const response = await fetch(`${apiBase}/models/${modelId}`);
			if (!response.ok) throw new Error('Failed to fetch model');
			model = await response.json();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load model';
		} finally {
			loading = false;
		}
	});
	
	async function handleSave() {
		try {
			isSaving = true;
			saveError = null;
			if (!model.name) {
				saveError = 'Model name is required';
				isSaving = false;
				return;
			}
			const modelId = $page.params.id;
			
			const modelData = {
				name: model.name,
				version: model.version || null,
				author: model.author || null,
				company: model.company || null,
				category: model.category || null,
				keywords: model.keywords || null,
				description: model.description || null
			};
			
			if (duplicateModel) {
				// Create a new model
				const response = await fetch(`${apiBase}/models`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(modelData)
				});
				if (!response.ok) throw new Error('Failed to create duplicate model');
				// Redirect to models list
				window.location.href = '/models';
			} else {
				// Update existing model
				const response = await fetch(`${apiBase}/models/${modelId}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(modelData)
				});
				if (!response.ok) throw new Error('Failed to update model');
				// Redirect back to models list
				window.location.href = '/models';
			}
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save model';
			isSaving = false;
		}
	}
	
	function handleCancel() {
		window.location.href = '/models';
	}
</script>

<!-- PAGE HEADER -->
<div id="application-content-area">
	<div class="page-title">
		<h1 class="heading heading_1">Edit Model</h1>
	</div>

	<div class="grid-row">
		<div class="grid-col grid-col_24">
			<div class="studies card">
				{#if loading}
					<div class="message">Loading model...</div>
				{:else if error}
					<div class="message message-error">Error: {error}</div>
				{:else}
					<form onsubmit={(e) => {
						e.preventDefault();
						handleSave();
					}}>
						{#if saveError}
							<div class="message message-error" style="margin-bottom: 20px;">Error: {saveError}</div>
						{/if}

						<div class="form-section">
							<div class="input">
								<input
									id="name"
									type="text"
									bind:value={model.name}
									class="input__text"
									class:input__text_changed={model.name && model.name.length > 0}
									placeholder=""
									required
								/>
								<label for="name" class="input__label">Name *</label>
							</div>

							<div class="input">
								<input
									id="version"
									type="text"
									bind:value={model.version}
									class="input__text"
									class:input__text_changed={model.version && model.version.length > 0}
								/>
								<label for="version" class="input__label">Version</label>
							</div>

							<div class="input">
								<input
									id="author"
									type="text"
									bind:value={model.author}
									class="input__text"
									class:input__text_changed={model.author && model.author.length > 0}
								/>
								<label for="author" class="input__label">Author</label>
							</div>

							<div class="input">
								<input
									id="company"
									type="text"
									bind:value={model.company}
									class="input__text"
									class:input__text_changed={model.company && model.company.length > 0}
								/>
								<label for="company" class="input__label">Company</label>
							</div>

							<div class="input">
								<input
									id="category"
									type="text"
									bind:value={model.category}
									class="input__text"
									class:input__text_changed={model.category && model.category.length > 0}
								/>
								<label for="category" class="input__label">Category</label>
							</div>

							<div class="input">
								<input
									id="keywords"
									type="text"
									bind:value={model.keywords}
									class="input__text"
									class:input__text_changed={model.keywords && model.keywords.length > 0}
								/>
								<label for="keywords" class="input__label">Keywords</label>
							</div>

							<div class="input">
							<textarea
								id="description"
								bind:value={model.description}
								class="input__text"
								class:input__text_changed={model.description && model.description.length > 0}
								rows="6"
							></textarea>
								<label for="description" class="input__label">Description</label>
							</div>
						</div>

						<div class="form-actions">
							<div style="margin-bottom: 16px; width: 100%;">
								<CheckboxField
									id="duplicate-model"
									bind:checked={duplicateModel}
									label="Duplicate"
									description="When checked, a new model will be created"
									disabled={isSaving}
								/>
							</div>
							<div style="display: flex; gap: 12px;">
								<button type="button" class="button button_secondary" onclick={handleCancel} disabled={isSaving}>
									Cancel
								</button>
								<button type="submit" class="button button_blue" disabled={isSaving}>
									{isSaving ? 'Saving...' : 'Save'}
								</button>
							</div>
						</div>
					</form>
				{/if}
			</div>
		</div>
	</div>
</div> <!-- end application-content-area -->

<style>
	.form-section {
		display: flex;
		flex-direction: column;
		gap: 24px;
		margin-bottom: 32px;
	}

	.form-actions {
		display: flex;
		gap: 12px;
		justify-content: flex-end;
		padding-top: 24px;
		border-top: 1px solid #eee;
	}

	:global(.input__text) {
		width: 100%;
	}

	textarea.input__text {
		font-family: inherit;
		resize: vertical;
	}

	:global(.button_blue) {
		background-color: #0066cc;
		color: white;
		border: none;
		padding: 10px 20px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 14px;
	}

	:global(.button_blue:hover) {
		background-color: #0052a3;
	}

	:global(.button_secondary) {
		background-color: #f0f0f0;
		color: #333;
		border: 1px solid #ccc;
		padding: 10px 20px;
		border-radius: 4px;
		cursor: pointer;
		font-size: 14px;
	}

	:global(.button_secondary:hover) {
		background-color: #e0e0e0;
	}
</style>
