<script lang="ts">
	import EntityDetailLayout from './EntityDetailLayout.svelte';
	import CheckboxField from './CheckboxField.svelte';
	import SingleSelect from './SingleSelect.svelte';
	import type { SelectItem } from '$lib/db';

	export let product: any = null;
	export let loading = false;
	export let error: string | null = null;
	export let saveError: string | null = null;
	export let isSaving = false;
	export let isEditing = false;
	export let orgItems: SelectItem[] = [];
	export let orgsLoading = false;
	export let selectedOrgId: string | null = null;
	export let selectedOrgName: string = '';
	export let onEdit: (() => void) | null = null;
	export let onCancel: (() => void) | null = null;
	export let onSave: ((e: Event) => void) | null = null;
</script>

<EntityDetailLayout
	{loading}
	{error}
	{isEditing}
	entityName="Product"
	pageTitle="Products"
	title={product?.device || ''}
	entity={product}
	{saveError}
	{isSaving}
	{onEdit}
	{onCancel}
	{onSave}
>
	<div slot="content">
		{#if isEditing}
			<div class="detail-section">
				<h3>Identification</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label for="product-device">Device</label>
						<div class="input">
							<input id="product-device" type="text" bind:value={product.device} class="input__text" class:input__text_changed={product.device?.length > 0} required />
						</div>
					</div>
					<div class="detail-field">
						<label for="product-submission">Submission Number</label>
						<div class="input">
							<input id="product-submission" type="text" bind:value={product.submission_number} class="input__text" class:input__text_changed={product.submission_number?.length > 0} required />
						</div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Company</span>
						<p>{product.company || '-'}</p>
					</div>
					<div class="detail-field">
						<label for="product-panel">Panel</label>
						<div class="input">
							<input id="product-panel" type="text" bind:value={product.panel} class="input__text" class:input__text_changed={product.panel?.length > 0} />
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<span class="detail-field__label">Organization</span>
						<SingleSelect items={orgItems} bind:selectedId={selectedOrgId} bind:selectedName={selectedOrgName} placeholder="Search organizations..." loading={orgsLoading} />
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label for="product-code">Primary Product Code</label>
						<div class="input">
							<input id="product-code" type="text" bind:value={product.primary_product_code} class="input__text" class:input__text_changed={product.primary_product_code?.length > 0} />
						</div>
					</div>
					<div class="detail-field">
						<label for="product-decision-date">Final Decision Date</label>
						<div class="input">
							<input id="product-decision-date" type="text" bind:value={product.date_of_final_decision} class="input__text" class:input__text_changed={product.date_of_final_decision?.length > 0} />
						</div>
					</div>
				</div>
				<div class="section-spacing-last">
					<CheckboxField id="product-process-flag" bind:checked={product.process_flag} label="Processed" description="Include this device in basis-threat generation" />
				</div>
			</div>

			<div class="detail-section">
				<h3>Clinical</h3>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="product-intended-use">Intended Use</label>
						<div class="input">
							<textarea id="product-intended-use" bind:value={product.intended_use} class="input__text" class:input__text_changed={product.intended_use?.length > 0}></textarea>
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="product-indications">Indications for Use</label>
						<div class="input">
							<textarea id="product-indications" bind:value={product.indications_for_use} class="input__text" class:input__text_changed={product.indications_for_use?.length > 0}></textarea>
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="product-description">Device Description</label>
						<div class="input">
							<textarea id="product-description" bind:value={product.device_description} class="input__text" class:input__text_changed={product.device_description?.length > 0}></textarea>
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Competitive</h3>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="product-superiority">Superiority</label>
						<div class="input">
							<textarea id="product-superiority" bind:value={product.superiority} class="input__text" class:input__text_changed={product.superiority?.length > 0}></textarea>
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="product-competitors">Competitors</label>
						<div class="input">
							<input id="product-competitors" type="text" bind:value={product.competitors} class="input__text" class:input__text_changed={product.competitors?.length > 0} />
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Contacts</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label for="product-contact-1">Contact 1</label>
						<div class="input"><input id="product-contact-1" type="text" bind:value={product.product_contact_1} class="input__text" class:input__text_changed={product.product_contact_1?.length > 0} /></div>
					</div>
					<div class="detail-field">
						<label for="product-contact-2">Contact 2</label>
						<div class="input"><input id="product-contact-2" type="text" bind:value={product.product_contact_2} class="input__text" class:input__text_changed={product.product_contact_2?.length > 0} /></div>
					</div>
					<div class="detail-field">
						<label for="product-contact-3">Contact 3</label>
						<div class="input"><input id="product-contact-3" type="text" bind:value={product.product_contact_3} class="input__text" class:input__text_changed={product.product_contact_3?.length > 0} /></div>
					</div>
				</div>
			</div>
		{:else}
			<div class="detail-section">
				<h3>Identification</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Device</span><p>{product.device || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Submission Number</span><p>{product.submission_number || '-'}</p></div>
				</div>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Company</span><p>{product.company || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Panel</span><p>{product.panel || '-'}</p></div>
				</div>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Organization</span><p>{selectedOrgName || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Primary Product Code</span><p>{product.primary_product_code || '-'}</p></div>
				</div>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Final Decision Date</span><p>{product.date_of_final_decision || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Processed</span><p>{product.process_flag ? 'Yes' : 'No'}</p></div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Clinical</h3>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Intended Use</span><p>{product.intended_use || '-'}</p></div></div>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Indications for Use</span><p>{product.indications_for_use || '-'}</p></div></div>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Device Description</span><p>{product.device_description || '-'}</p></div></div>
			</div>

			<div class="detail-section">
				<h3>Competitive</h3>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Superiority</span><p>{product.superiority || '-'}</p></div></div>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Competitors</span><p>{product.competitors || '-'}</p></div></div>
			</div>

			<div class="detail-section">
				<h3>Contacts</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Contact 1</span><p>{product.product_contact_1 || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Contact 2</span><p>{product.product_contact_2 || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Contact 3</span><p>{product.product_contact_3 || '-'}</p></div>
				</div>
			</div>
		{/if}
	</div>
</EntityDetailLayout>
