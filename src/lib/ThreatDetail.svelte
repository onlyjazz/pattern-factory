<script lang="ts">
	import EntityDetailLayout from './EntityDetailLayout.svelte';
	import CheckboxField from './CheckboxField.svelte';
	import SingleSelect from './SingleSelect.svelte';
	import type { SelectItem } from './SingleSelect.svelte';

	export let threat: any = null;
	export let loading = false;
	export let error: string | null = null;
	export let saveError: string | null = null;
	export let isSaving = false;
	export let isEditing = false;
	export let cardItems: SelectItem[] = [];
	export let cardsLoading = false;
	export let selectedCardId: string | null = null;
	export let selectedCardName: string = '';
	export let onEdit: (() => void) | null = null;
	export let onCancel: (() => void) | null = null;
	export let onSave: ((e: Event) => void) | null = null;
</script>

<EntityDetailLayout
	{loading}
	{error}
	{isEditing}
	entityName="Threat"
	pageTitle="Risks"
	entity={threat}
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
						<div class="input">
							<input
								id="threat-tag"
								type="text"
								bind:value={threat.tag}
								class="input__text"
								class:input__text_changed={threat.tag?.length > 0}
							/>
						</div>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label>Description</label>
						<div class="input">
							<input
								id="threat-description"
								type="text"
								bind:value={threat.description}
								class="input__text"
								class:input__text_changed={threat.description?.length > 0}
								required
							/>
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label>Associated Card</label>
						<SingleSelect
							items={cardItems}
							bind:selectedId={selectedCardId}
							bind:selectedName={selectedCardName}
							placeholder="Search cards..."
							loading={cardsLoading}
						/>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Threat Metrics</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Probability</label>
						<p>{threat.probability || '-'}</p>
					</div>
					<div class="detail-field">
						<label>Mitigation Level</label>
						<p>{threat.mitigation_level || '-'}</p>
					</div>
					<div class="detail-field">
						<label>Disabled</label>
						<div style="margin-top: 8px;">
							<CheckboxField
								id="threat-disabled"
								bind:checked={threat.disabled}
								label="Disable the risk"
							/>
						</div>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label>Damage Description</label>
						<div class="input">
							<input
								id="threat-damage-description"
								type="text"
								bind:value={threat.damage_description}
								class="input__text"
								class:input__text_changed={threat.damage_description?.length > 0}
							/>
						</div>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Metadata</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Domain</label>
						<div class="input">
							<input
								id="threat-domain"
								type="text"
								bind:value={threat.domain}
								class="input__text"
								class:input__text_changed={threat.domain?.length > 0}
							/>
						</div>
					</div>
					<div class="detail-field">
						<label>Version</label>
						<p>{threat.version || '-'}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>STRIDE Classification</h3>
				<div class="stride-grid">
					<div class="detail-field">
						<CheckboxField
							id="threat-spoofing"
							bind:checked={threat.spoofing}
							label="Spoofing"
						/>
					</div>
					<div class="detail-field">
						<CheckboxField
							id="threat-tampering"
							bind:checked={threat.tampering}
							label="Tampering"
						/>
					</div>
					<div class="detail-field">
						<CheckboxField
							id="threat-repudiation"
							bind:checked={threat.repudiation}
							label="Repudiation"
						/>
					</div>
					<div class="detail-field">
						<CheckboxField
							id="threat-information-disclosure"
							bind:checked={threat.information_disclosure}
							label="Info Disclosure"
						/>
					</div>
					<div class="detail-field">
						<CheckboxField
							id="threat-denial-of-service"
							bind:checked={threat.denial_of_service}
							label="Denial of Service"
						/>
					</div>
					<div class="detail-field">
						<CheckboxField
							id="threat-elevation-of-privilege"
							bind:checked={threat.elevation_of_privilege}
							label="Elevation of Privilege"
						/>
					</div>
				</div>
			</div>
		{:else}
			<div class="detail-section">
				<h3>Basic Information</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Tag</label>
						<p>{threat.tag || '-'}</p>
					</div>
				</div>
				<div class="detail-row">
					<div class="detail-field">
						<label>Description</label>
						<p>{threat.description}</p>
					</div>
				</div>
				{#if threat.card}
					<div class="detail-row full">
						<div class="detail-field">
							<label>Associated Card</label>
							<h4 style="margin: 8px 0 0 0; font-size: 15px; font-weight: 500; color: #333;">
								{threat.card.name}
								<a href="/cards/view/story/{threat.card.id}" target="_blank" rel="noopener noreferrer" title="View card details" style="font-size: 9px; color: #0066cc; text-decoration: none; vertical-align: super; margin-left: 2px;">
									↗
								</a>
							</h4>
							<p style="margin-top: 8px;">{threat.card.description}</p>
						</div>
					</div>
				{/if}
			</div>

			<div class="detail-section">
				<h3>Threat Metrics</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Probability</label>
						<p>{threat.probability || '-'}</p>
					</div>
					<div class="detail-field">
						<label>Mitigation Level</label>
						<p>{threat.mitigation_level || '-'}</p>
					</div>
					<div class="detail-field">
						<label>Disabled</label>
						<p>{threat.disabled ? 'Yes' : 'No'}</p>
					</div>
				</div>
				<div class="detail-row full">
					<div class="detail-field">
						<label>Damage Description</label>
						<p>{threat.damage_description || '-'}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>Metadata</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Domain</label>
						<p>{threat.domain || '-'}</p>
					</div>
					<div class="detail-field">
						<label>Version</label>
						<p>{threat.version || '-'}</p>
					</div>
				</div>
			</div>

			<div class="detail-section">
				<h3>STRIDE Classification</h3>
				<div class="detail-row">
					<div class="detail-field">
						<label>Spoofing</label>
						<p>{threat.spoofing ? '✓' : '✗'}</p>
					</div>
					<div class="detail-field">
						<label>Tampering</label>
						<p>{threat.tampering ? '✓' : '✗'}</p>
					</div>
					<div class="detail-field">
						<label>Repudiation</label>
						<p>{threat.repudiation ? '✓' : '✗'}</p>
					</div>
					<div class="detail-field">
						<label>Info Disclosure</label>
						<p>{threat.information_disclosure ? '✓' : '✗'}</p>
					</div>
					<div class="detail-field">
						<label>Denial of Service</label>
						<p>{threat.denial_of_service ? '✓' : '✗'}</p>
					</div>
					<div class="detail-field">
						<label>Elevation of Privilege</label>
						<p>{threat.elevation_of_privilege ? '✓' : '✗'}</p>
					</div>
				</div>
			</div>
		{/if}
	</div>
</EntityDetailLayout>
