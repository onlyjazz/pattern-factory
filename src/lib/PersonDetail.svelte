<script lang="ts">
	import EntityDetailLayout from './EntityDetailLayout.svelte';
	import SingleSelect from './SingleSelect.svelte';
	import type { SelectItem } from '$lib/db';

	export let person: any = null;
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
	entityName="Person"
	pageTitle="People"
	entity={person}
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
						<label for="person-name">Name</label>
						<div class="input">
							<input id="person-name" type="text" bind:value={person.name} class="input__text" class:input__text_changed={person.name?.length > 0} required />
						</div>
					</div>
					<div class="detail-field">
						<label for="person-job">Job Description</label>
						<div class="input">
							<input id="person-job" type="text" bind:value={person.job_description} class="input__text" class:input__text_changed={person.job_description?.length > 0} />
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<span class="detail-field__label">Organization</span>
						<SingleSelect items={orgItems} bind:selectedId={selectedOrgId} bind:selectedName={selectedOrgName} placeholder="Search organizations..." loading={orgsLoading} />
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="person-description">Description</label>
						<div class="input">
							<textarea id="person-description" bind:value={person.description} class="input__text" class:input__text_changed={person.description?.length > 0}></textarea>
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Contact</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label for="person-email">Email</label>
						<div class="input"><input id="person-email" type="text" bind:value={person.email} class="input__text" class:input__text_changed={person.email?.length > 0} /></div>
					</div>
					<div class="detail-field">
						<label for="person-linkedin">LinkedIn URL</label>
						<div class="input"><input id="person-linkedin" type="text" bind:value={person.linkedin_url} class="input__text" class:input__text_changed={person.linkedin_url?.length > 0} /></div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label for="person-company-url">Company URL</label>
						<div class="input"><input id="person-company-url" type="text" bind:value={person.company_url} class="input__text" class:input__text_changed={person.company_url?.length > 0} /></div>
					</div>
					<div class="detail-field">
						<label for="person-source">Content Source</label>
						<div class="input"><input id="person-source" type="text" bind:value={person.content_source} class="input__text" class:input__text_changed={person.content_source?.length > 0} /></div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label for="person-content-url">Content URL</label>
						<div class="input"><input id="person-content-url" type="text" bind:value={person.content_url} class="input__text" class:input__text_changed={person.content_url?.length > 0} /></div>
					</div>
				</div>
			</div>
		{:else}
			<div class="detail-section">
				<h3>Identity</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Name</span><p>{person.name || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Job Description</span><p>{person.job_description || '-'}</p></div>
				</div>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Organization</span><p>{selectedOrgName || '-'}</p></div></div>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Description</span><p>{person.description || '-'}</p></div></div>
			</div>

			<div class="detail-section">
				<h3>Contact</h3>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Email</span><p>{person.email || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">LinkedIn URL</span><p>{person.linkedin_url || '-'}</p></div>
				</div>
				<div class="detail-row">
					<div class="detail-field"><span class="detail-field__label">Company URL</span><p>{person.company_url || '-'}</p></div>
					<div class="detail-field"><span class="detail-field__label">Content Source</span><p>{person.content_source || '-'}</p></div>
				</div>
				<div class="detail-row full"><div class="detail-field"><span class="detail-field__label">Content URL</span><p>{person.content_url || '-'}</p></div></div>
			</div>
		{/if}
	</div>
</EntityDetailLayout>
