<script lang="ts">
	import EntityDetailLayout from './EntityDetailLayout.svelte';
	import CheckboxField from './CheckboxField.svelte';

	export let countermeasure: any = null;
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
	entityName="Countermeasure"
	pageTitle="Countermeasures"
	entity={countermeasure}
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
						<label>Tag</label>
						<p>C{countermeasure.id}</p>
					</div>
					<div class="detail-field">
						<label>Version</label>
						<p>{countermeasure.version || 1}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label>Name</label>
						<div class="input">
							<input
								id="countermeasure-name"
								type="text"
								bind:value={countermeasure.name}
								class="input__text"
								class:input__text_changed={countermeasure.name?.length > 0}
								required
							/>
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Details</h3>
				<div class="detail-row">
					<div class="detail-field full">
						<label>Description</label>
						<div class="input">
							<input
								id="countermeasure-description"
								type="text"
								bind:value={countermeasure.description}
								class="input__text"
								class:input__text_changed={countermeasure.description?.length > 0}
							/>
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Cost Configuration</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Fixed Implementation Cost ($)</label>
						<div class="input">
							<input
								id="fixed-implementation-cost"
								type="number"
								bind:value={countermeasure.fixed_implementation_cost}
								class="input__text"
								class:input__text_changed={countermeasure.fixed_implementation_cost}
								min="0"
							/>
						</div>
					</div>
					<div class="detail-field">
						<label>Fixed Cost Period (months)</label>
						<div class="input">
							<input
								id="fixed-cost-period"
								type="number"
								bind:value={countermeasure.fixed_cost_period}
								class="input__text"
								class:input__text_changed={countermeasure.fixed_cost_period}
								min="1"
							/>
						</div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label>Recurring Implementation Cost ($/year)</label>
						<div class="input">
							<input
								id="recurring-implementation-cost"
								type="number"
								bind:value={countermeasure.recurring_implementation_cost}
								class="input__text"
								class:input__text_changed={countermeasure.recurring_implementation_cost}
								min="0"
							/>
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Cost Options</h3>
				<div style="margin-bottom: 1.5rem;">
					<CheckboxField
						id="include-fixed-cost"
						bind:checked={countermeasure.include_fixed_cost}
						label="Include fixed cost"
						description="When checked the risk assessment will include the fixed cost"
					/>
				</div>

				<div style="margin-bottom: 0;">
					<CheckboxField
						id="include-recurring-cost"
						bind:checked={countermeasure.include_recurring_cost}
						label="Include recurring cost"
						description="When checked the risk assessment will include the recurring cost on a yearly basis"
					/>
				</div>
			</div>

			<div class="detail-section">
				<h3>Status</h3>
				<div style="margin-bottom: 1.5rem;">
					<CheckboxField
						id="implemented"
						bind:checked={countermeasure.implemented}
						label="Implemented"
						description="Check if you've already implemented this countermeasure"
					/>
				</div>

				<div style="margin-bottom: 0;">
					<CheckboxField
						id="disabled"
						bind:checked={countermeasure.disabled}
						label="Exclude"
						description="When clicking this checkbox, you will exclude the countermeasure from the risk mitigation set"
					/>
				</div>
			</div>
		{:else}
			<div class="detail-section">
				<h3>Basic Information</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Tag</label>
						<p>C{countermeasure.id}</p>
					</div>
					<div class="detail-field">
						<label>Version</label>
						<p>{countermeasure.version || 1}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label>Name</label>
						<p>{countermeasure.name}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Details</h3>
				<div class="detail-row">
					<div class="detail-field full">
						<label>Description</label>
						<p>{countermeasure.description || '-'}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Cost Configuration</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Fixed Implementation Cost</label>
						<p>${countermeasure.fixed_implementation_cost || 0}</p>
					</div>
					<div class="detail-field">
						<label>Fixed Cost Period (months)</label>
						<p>{countermeasure.fixed_cost_period || 12}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label>Recurring Implementation Cost</label>
						<p>${countermeasure.recurring_implementation_cost || 0}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Cost Options</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Include Fixed Cost</label>
						<p>{countermeasure.include_fixed_cost ? 'Yes' : 'No'}</p>
					</div>
					<div class="detail-field">
						<label>Include Recurring Cost</label>
						<p>{countermeasure.include_recurring_cost ? 'Yes' : 'No'}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Status</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Implemented</label>
						<p>{countermeasure.implemented ? 'Yes' : 'No'}</p>
					</div>
					<div class="detail-field">
						<label>Exclude</label>
						<p>{countermeasure.disabled ? 'Yes' : 'No'}</p>
					</div>
				</div>
			</div>
		{/if}
	</div>
</EntityDetailLayout>
