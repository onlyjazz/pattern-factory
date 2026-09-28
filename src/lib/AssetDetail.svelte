<script lang="ts">
	import EntityDetailLayout from './EntityDetailLayout.svelte';
	import CheckboxField from './CheckboxField.svelte';

	export let asset: any = null;
	export let loading = false;
	export let error: string | null = null;
	export let saveError: string | null = null;
	export let isSaving = false;
	export let isEditing = false;
	export let onEdit: (() => void) | null = null;
	export let onCancel: (() => void) | null = null;
	export let onSave: ((e: Event) => void) | null = null;
</script>

<EntityDetailLayout
	{loading}
	{error}
	{isEditing}
	entityName="Asset"
	pageTitle="Model assets"
	entity={asset}
	{saveError}
	{isSaving}
	{onEdit}
	{onCancel}
	{onSave}
>
	<div slot="content">
		{#if isEditing}
			<div class="detail-section">
				<h3>Basic Information</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label for="asset-tag">Tag</label>
						<div class="input">
							<input
								id="asset-tag"
								type="text"
								bind:value={asset.tag}
								class="input__text"
								class:input__text_changed={asset.tag?.length > 0}
							/>
						</div>
					</div>
					<div class="detail-field">
						<span class="detail-field__label">Version</span>
						<p>{asset.version || 1}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label for="asset-name">Name</label>
						<div class="input">
							<input
								id="asset-name"
								type="text"
								bind:value={asset.name}
								class="input__text"
								class:input__text_changed={asset.name?.length > 0}
								required
							/>
						</div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field full">
						<label for="asset-description">Description</label>
						<div class="input">
							<input
								id="asset-description"
								type="text"
								bind:value={asset.description}
								class="input__text"
								class:input__text_changed={asset.description?.length > 0}
							/>
						</div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Yearly Value (Computed)</span>
						<p>{(asset.yearly_value || 0).toLocaleString()}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Financial Configuration</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label for="fixed-value">Fixed Value</label>
						<div class="input">
							<input
								id="fixed-value"
								type="number"
								bind:value={asset.fixed_value}
								class="input__text"
								class:input__text_changed={asset.fixed_value}
								min="0"
							/>
						</div>
					</div>
					<div class="detail-field">
						<label for="fixed-value-period">Fixed Value Period (months)</label>
						<div class="input">
							<input
								id="fixed-value-period"
								type="number"
								bind:value={asset.fixed_value_period}
								class="input__text"
								class:input__text_changed={asset.fixed_value_period}
								min="1"
							/>
						</div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label for="recurring-value">Recurring Value</label>
						<div class="input">
							<input
								id="recurring-value"
								type="number"
								bind:value={asset.recurring_value}
								class="input__text"
								class:input__text_changed={asset.recurring_value}
								min="0"
							/>
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Options</h3>
				<div class="section-spacing">
					<CheckboxField
						id="include-fixed-value"
						bind:checked={asset.include_fixed_value}
						label="Include fixed value"
						description="When checked the yearly value will include the fixed value"
					/>
				</div>

				<div class="section-spacing">
					<CheckboxField
						id="include-recurring-value"
						bind:checked={asset.include_recurring_value}
						label="Include recurring value"
						description="When checked the yearly value will include the recurring value"
					/>
				</div>

				<div class="section-spacing-last">
					<CheckboxField
						id="exclude-asset"
						bind:checked={asset.disabled}
						label="Exclude asset"
						description="When checked the asset will be excluded from the threat model"
					/>
				</div>
			</div>
		{:else}
			<div class="detail-section">
				<h3>Basic Information</h3>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Tag</span>
						<p>{asset.tag || '-'}</p>
					</div>
					<div class="detail-field">
						<span class="detail-field__label">Version</span>
						<p>{asset.version || '-'}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Name</span>
						<p>{asset.name}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field full">
						<span class="detail-field__label">Description</span>
						<p>{asset.description || '-'}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Yearly Value (Computed)</span>
						<p>{(asset.yearly_value || 0).toLocaleString()}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Financial Configuration</h3>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Fixed Value</span>
						<p>{(asset.fixed_value || 0).toLocaleString()}</p>
					</div>
					<div class="detail-field">
						<span class="detail-field__label">Fixed Value Period (months)</span>
						<p>{asset.fixed_value_period || 12}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Recurring Value</span>
						<p>{(asset.recurring_value || 0).toLocaleString()}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Options</h3>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Include Fixed Value</span>
						<p>{asset.include_fixed_value ? 'Yes' : 'No'}</p>
					</div>
					<div class="detail-field">
						<span class="detail-field__label">Include Recurring Value</span>
						<p>{asset.include_recurring_value ? 'Yes' : 'No'}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Exclude asset</span>
						<p>{asset.disabled ? 'Yes' : 'No'}</p>
					</div>
				</div>
			</div>
		{/if}
	</div>
</EntityDetailLayout>
