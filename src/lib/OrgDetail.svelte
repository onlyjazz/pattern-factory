<script lang="ts">
	import EntityDetailLayout from './EntityDetailLayout.svelte';
	import SingleSelect from './SingleSelect.svelte';
	import type { SelectItem } from '$lib/db';

	export let org: any = null;
	export let loading = false;
	export let error: string | null = null;
	export let saveError: string | null = null;
	export let isSaving = false;
	export let isEditing = false;
	export let statusItems: SelectItem[] = [];
	export let statusesLoading = false;
	export let selectedStatusId: string | null = null;
	export let selectedStatusName: string = '';
	export let onEdit: (() => void) | null = null;
	export let onCancel: (() => void) | null = null;
	export let onSave: ((e: Event) => void) | null = null;
</script>

<EntityDetailLayout
	{loading}
	{error}
	{isEditing}
	entityName="Organization"
	pageTitle="Orgs"
	entity={org}
	{saveError}
	{isSaving}
	{onEdit}
	{onCancel}
	{onSave}
>
	<div slot="content">
		{#if isEditing}
			<div class="detail-section">
				<h3>Identity</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label for="org-name">Name</label>
						<div class="input">
							<input id="org-name" type="text" bind:value={org.name} class="input__text" class:input__text_changed={org.name?.length > 0} required />
						</div>
					</div>
					<div class="detail-field">
						<label for="org-name-before">Name Before Acquisition</label>
						<div class="input">
							<input id="org-name-before" type="text" bind:value={org.name_before_acquisition} class="input__text" class:input__text_changed={org.name_before_acquisition?.length > 0} />
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="org-description">Description</label>
						<div class="input">
							<textarea id="org-description" bind:value={org.description} class="input__text" class:input__text_changed={org.description?.length > 0}></textarea>
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Classification</h3>
				<div class="detail-row">
					<div class="detail-field">
						<span class="detail-field__label">Status</span>
						<SingleSelect items={statusItems} bind:selectedId={selectedStatusId} bind:selectedName={selectedStatusName} placeholder="Select status..." loading={statusesLoading} searchable={false} />
					</div>
					<div class="detail-field">
						<label for="org-stage">Stage</label>
						<div class="input">
							<input id="org-stage" type="text" bind:value={org.stage} class="input__text" class:input__text_changed={org.stage?.length > 0} />
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Financials</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label for="org-funding">Funding</label>
						<div class="input"><input id="org-funding" type="number" min="0" bind:value={org.funding} class="input__text" class:input__text_changed={org.funding} /></div>
					</div>
					<div class="detail-field">
						<label for="org-sales">Estimated Annual Sales</label>
						<div class="input"><input id="org-sales" type="number" min="0" bind:value={org.estimated_annual_sales} class="input__text" class:input__text_changed={org.estimated_annual_sales} /></div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label for="org-employees">Employees</label>
						<div class="input"><input id="org-employees" type="number" min="0" bind:value={org.employees} class="input__text" class:input__text_changed={org.employees} /></div>
					</div>
					<div class="detail-field">
						<label for="org-hq">Headquarters</label>
						<div class="input"><input id="org-hq" type="text" bind:value={org.headquarters} class="input__text" class:input__text_changed={org.headquarters?.length > 0} /></div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label for="org-founded">Date Founded</label>
						<div class="input"><input id="org-founded" type="text" bind:value={org.date_founded} class="input__text" class:input__text_changed={org.date_founded?.length > 0} /></div>
					</div>
					<div class="detail-field">
						<label for="org-linkedin">LinkedIn Company URL</label>
						<div class="input"><input id="org-linkedin" type="text" bind:value={org.linkedin_company_url} class="input__text" class:input__text_changed={org.linkedin_company_url?.length > 0} /></div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Index</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Size (computed)</span><p>{(org.size || 0).toLocaleString()}</p></div>
					<div class="detail-field"><span class="detail-field__label">Tier (computed)</span><p>{org.tier ?? '-'}</p></div>
				</div>
			</div>
		{:else}
			<div class="detail-section">
				<h3>Identity</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Name</span><p>{org.name || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Name Before Acquisition</span><p>{org.name_before_acquisition || '-'}</p></div>
				</div>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Description</span><p>{org.description || '-'}</p></div></div>
			</div>

			<div class="detail-section">
				<h3>Classification</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Status</span><p>{selectedStatusName || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Stage</span><p>{org.stage || '-'}</p></div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Financials</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Funding</span><p>{(org.funding || 0).toLocaleString()}</p></div>
					<div class="detail-field"><span class="detail-field__label">Estimated Annual Sales</span><p>{(org.estimated_annual_sales || 0).toLocaleString()}</p></div>
				</div>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Employees</span><p>{org.employees ?? '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Headquarters</span><p>{org.headquarters || '-'}</p></div>
				</div>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Date Founded</span><p>{org.date_founded || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">LinkedIn Company URL</span><p>{org.linkedin_company_url || '-'}</p></div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Index</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Size (computed)</span><p>{(org.size || 0).toLocaleString()}</p></div>
					<div class="detail-field"><span class="detail-field__label">Tier (computed)</span><p>{org.tier ?? '-'}</p></div>
				</div>
			</div>
		{/if}
	</div>
</EntityDetailLayout>
