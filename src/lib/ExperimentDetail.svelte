<script lang="ts">
	import EntityDetailLayout from './EntityDetailLayout.svelte';
	import ExperimentStepsEditor from './ExperimentStepsEditor.svelte';
	import ProductMultiSelect from './ProductMultiSelect.svelte';
	import ExperimentSendPanel from './ExperimentSendPanel.svelte';
	import RichTextEditor from './RichTextEditor.svelte';
	import { richTextToHtml } from '$lib/richText';
	import type { StartExperimentResult } from '$lib/closeSend';
	import type { Experiment } from '$lib/types/models';
	import {
		ARM_OPTIONS,
		EMAIL_HEADER_STATUS_OPTIONS,
		armLabel,
		type ProductOption
	} from '$lib/experiments';

	export let experiment: Experiment | null = null;
	export let loading = false;
	export let error: string | null = null;
	export let saveError: string | null = null;
	export let isSaving = false;
	export let isEditing = false;
	export let productItems: ProductOption[] = [];
	export let productsLoading = false;
	export let onEdit: (() => void) | null = null;
	export let onCancel: (() => void) | null = null;
	export let onSave: ((e: Event) => void) | null = null;
	export let sending = false;
	export let sendError: string | null = null;
	export let sendResult: StartExperimentResult | null = null;
	export let sendCount = 0;
	export let onSend: (() => void) | null = null;

	$: selectedProductNames = (experiment?.product_ids ?? []).map(
		(id) => productItems.find((product) => product.id === id)?.name ?? `#${id}`
	);
	$: hasSteps = (experiment?.steps?.length ?? 0) > 0;
</script>

<EntityDetailLayout
	{loading}
	{error}
	{isEditing}
	entityName="Experiment"
	pageTitle="Experiments"
	title={experiment?.name || ''}
	entity={experiment}
	{saveError}
	{isSaving}
	{onEdit}
	{onCancel}
	{onSave}
>
	<div slot="content">
		{#if isEditing && experiment}
			<div class="detail-section">
				<h3>Definition</h3>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="experiment-name">Name</label>
						<div class="input">
							<input id="experiment-name" type="text" bind:value={experiment.name} class="input__text" class:input__text_changed={experiment.name?.length > 0} required />
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<RichTextEditor
							label="Description"
							placeholder="Paste a Close template candidate..."
							bind:value={experiment.description}
						/>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label for="experiment-arm">Arm</label>
						<div class="input input_select">
							<select id="experiment-arm" bind:value={experiment.arm} class="input__text" class:input__text_changed={true}>
								{#each ARM_OPTIONS as option}
									<option value={option.value}>{option.label}</option>
								{/each}
							</select>
						</div>
					</div>
					<div class="detail-field">
						<label for="experiment-email-status">Email Header Status</label>
						<div class="input input_select">
							<select id="experiment-email-status" bind:value={experiment.email_header_status} class="input__text" class:input__text_changed={true}>
								{#each EMAIL_HEADER_STATUS_OPTIONS as status}
									<option value={status}>{status}</option>
								{/each}
							</select>
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<RichTextEditor
							label="Email Header"
							placeholder="Paste the email header copy..."
							bind:value={experiment.email_header}
						/>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Steps</h3>
				<ExperimentStepsEditor bind:steps={experiment.steps} />
			</div>

			<div class="detail-section section-spacing-last">
				<h3>Products</h3>
				<ProductMultiSelect items={productItems} loading={productsLoading} bind:selectedIds={experiment.product_ids} />
			</div>
		{:else if experiment}
			<ExperimentSendPanel {sendCount} {hasSteps} {sending} {sendError} {sendResult} {onSend} />

			<div class="detail-section">
				<h3>Definition</h3>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Name</span><p>{experiment.name || '-'}</p></div></div>
				<div class="detail-row full">
					<div class="detail-field">
						<span class="detail-field__label">Description</span>
						{#if experiment.description}
							<div class="rich-text-content">{@html richTextToHtml(experiment.description)}</div>
						{:else}
							<p>-</p>
						{/if}
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Arm</span><p>{armLabel(experiment.arm)}</p></div>
					<div class="detail-field"><span class="detail-field__label">Email Header Status</span><p>{experiment.email_header_status}</p></div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<span class="detail-field__label">Email Header</span>
						{#if experiment.email_header}
							<div class="rich-text-content">{@html richTextToHtml(experiment.email_header)}</div>
						{:else}
							<p>-</p>
						{/if}
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Steps</h3>
				{#if experiment.steps.length === 0}
					<p class="help-text">No steps configured.</p>
				{:else}
					<div class="table">
						<table>
							<thead>
								<tr>
									<th class="tal">Position</th>
									<th class="tal">Channel</th>
									<th class="tal">Content ID</th>
									<th class="tal">Content Rev</th>
								</tr>
							</thead>
							<tbody>
								{#each experiment.steps as step (step.position)}
									<tr>
										<td class="tal">{step.position}</td>
										<td class="tal">{step.channel}</td>
										<td class="tal">{step.content_id || '-'}</td>
										<td class="tal">{step.content_rev || '-'}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>

			<div class="detail-section section-spacing-last">
				<h3>Products</h3>
				{#if selectedProductNames.length === 0}
					<p class="help-text">No products assigned.</p>
				{:else}
					<p>{selectedProductNames.join(', ')}</p>
				{/if}
			</div>
		{/if}
	</div>
</EntityDetailLayout>
