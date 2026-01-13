<script lang="ts">
	import { onMount } from 'svelte';
	import type { Threat, Card } from '$lib/db';
	import { marked } from 'marked';
	
	let threatId: string;
	let threat: Threat | null = null;
	let loading = true;
	let error: string | null = null;
	let saveError: string | null = null;
	let isEditing = false;
	let editThreat: Partial<Threat> = {};
	let allCards: Card[] = [];
	let cardSearchQuery = '';
	let filteredCards: Card[] = [];
	let showCardDropdown = false;
	let selectedCardIds: Set<string> = new Set();
	
	const apiBase = 'http://localhost:8000';
	
	onMount(async () => {
		const pathParts = window.location.pathname.split('/');
		threatId = pathParts[pathParts.length - 1];
		
		try {
			// Load threat
			const threatResponse = await fetch(`${apiBase}/threats/${threatId}`);
			if (!threatResponse.ok) throw new Error('Failed to fetch threat');
			threat = await threatResponse.json();
			threat.id = String(threat.id);
			
			// Load all cards
			const cardsResponse = await fetch(`${apiBase}/cards`);
			if (!cardsResponse.ok) throw new Error('Failed to fetch cards');
			allCards = await cardsResponse.json();
			
			if (threat && threat.cards) {
				selectedCardIds = new Set(threat.cards.map(c => String(c.id)));
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});
	
	function startEdit() {
		editThreat = { ...threat };
		selectedCardIds = new Set((threat?.cards || []).map(c => String(c.id)));
		isEditing = true;
	}
	
	function cancelEdit() {
		isEditing = false;
		editThreat = {};
		selectedCardIds = new Set();
		cardSearchQuery = '';
		filteredCards = [];
		saveError = null;
	}
	
	function searchCards(query: string) {
		if (!query.trim()) {
			filteredCards = [];
			showCardDropdown = false;
			return;
		}
		
		filteredCards = allCards.filter(c =>
			c.name.toLowerCase().includes(query.toLowerCase()) ||
			c.description.toLowerCase().includes(query.toLowerCase())
		);
		showCardDropdown = true;
	}
	
	function toggleCard(card: Card) {
		const cardId = String(card.id);
		if (selectedCardIds.has(cardId)) {
			selectedCardIds.delete(cardId);
		} else {
			selectedCardIds.add(cardId);
		}
		selectedCardIds = selectedCardIds;
	}
	
	async function handleSave() {
		try {
			saveError = null;
			const response = await fetch(`${apiBase}/threats/${threat?.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: editThreat.name,
					description: editThreat.description,
					scenario: editThreat.scenario || null,
					probability: editThreat.probability || null,
					damage_description: editThreat.damage_description || null,
					spoofing: editThreat.spoofing,
					tampering: editThreat.tampering,
					repudiation: editThreat.repudiation,
					information_disclosure: editThreat.information_disclosure,
					denial_of_service: editThreat.denial_of_service,
					elevation_of_privilege: editThreat.elevation_of_privilege,
					mitigation_level: editThreat.mitigation_level,
					disabled: editThreat.disabled,
					card_ids: Array.from(selectedCardIds)
				})
			});
			if (!response.ok) throw new Error('Failed to save threat');
			const updated = await response.json();
			threat = { ...updated, id: String(updated.id) };
			if (threat && threat.cards) {
				selectedCardIds = new Set(threat.cards.map(c => String(c.id)));
			}
			isEditing = false;
		} catch (e) {
			saveError = e instanceof Error ? e.message : 'Failed to save threat';
		}
	}

</script>

<div id="application-content-area">
	<div class="page-title">
		<a href="/threats" class="back-link">← Back to Threats</a>
		<h1 class="heading heading_1">{threat?.name || 'Loading...'}</h1>
	</div>

	{#if loading}
		<div class="message">Loading threat...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if threat}
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="card threat-detail-card">
					{#if !isEditing}
						<div class="view-mode">
							<div class="card-header-actions">
								<button class="button button_green" onclick={startEdit}>
									Edit
								</button>
							</div>
							
							<div class="detail-section">
								<h3>Basic Information</h3>
								<div class="detail-row">
									<div class="detail-field">
										<label>Name</label>
										<p>{threat.name}</p>
									</div>
									<div class="detail-field">
										<label>Description</label>
										<p>{threat.description}</p>
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
										<p>{threat.disabled ? 'Yes' : 'No'}</p>
									</div>
								</div>
								<div class="detail-row">
									<div class="detail-field full">
										<label>Damage Description</label>
										<p>{threat.damage_description || '-'}</p>
									</div>
								</div>
							</div>
							
							<div class="detail-section">
								<h3>STRIDE Classification</h3>
								<div class="stride-display">
									<div class="stride-item" class:active={threat.spoofing}>Spoofing: {threat.spoofing ? '✓' : '✗'}</div>
									<div class="stride-item" class:active={threat.tampering}>Tampering: {threat.tampering ? '✓' : '✗'}</div>
									<div class="stride-item" class:active={threat.repudiation}>Repudiation: {threat.repudiation ? '✓' : '✗'}</div>
									<div class="stride-item" class:active={threat.information_disclosure}>Info Disclosure: {threat.information_disclosure ? '✓' : '✗'}</div>
									<div class="stride-item" class:active={threat.denial_of_service}>Denial of Service: {threat.denial_of_service ? '✓' : '✗'}</div>
									<div class="stride-item" class:active={threat.elevation_of_privilege}>Elevation of Privilege: {threat.elevation_of_privilege ? '✓' : '✗'}</div>
								</div>
							</div>
							
							{#if threat.cards && threat.cards.length > 0}
								<div class="detail-section">
									<h3>Related Cards ({threat.cards.length})</h3>
									<div class="cards-list">
										{#each threat.cards as card}
											<div class="card-item">
												<div class="card-name">{card.name}</div>
												<div class="card-description">{card.description}</div>
											</div>
										{/each}
									</div>
								</div>
							{/if}
							
							{#if threat.scenario}
								<div class="detail-section">
									<h3>Scenario</h3>
									<div class="scenario-content">
										{@html marked(threat.scenario)}
									</div>
								</div>
							{/if}
						</div>
					{:else}
						<div class="edit-mode">
							{#if saveError}
								<div class="message message-error" style="margin-bottom: 20px;">Error: {saveError}</div>
							{/if}
							
							<div class="edit-form">
								<div class="form-section">
									<h3>Basic Information</h3>
									<div class="input">
										<input
											id="edit-name"
											type="text"
											bind:value={editThreat.name}
											class="input__text"
											class:input__text_changed={editThreat.name?.length > 0}
											required
										/>
										<label for="edit-name" class="input__label">Name</label>
									</div>

									<div class="input">
										<input
											id="edit-description"
											type="text"
											bind:value={editThreat.description}
											class="input__text"
											class:input__text_changed={editThreat.description?.length > 0}
											required
										/>
										<label for="edit-description" class="input__label">Description</label>
									</div>
								</div>

								<div class="form-section">
									<h3>Threat Metrics</h3>
									<div class="input">
										<input
											id="edit-probability"
											type="number"
											bind:value={editThreat.probability}
											class="input__text"
										/>
										<label for="edit-probability" class="input__label">Probability</label>
									</div>

									<div class="input">
										<input
											id="edit-damage-description"
											type="text"
											bind:value={editThreat.damage_description}
											class="input__text"
											class:input__text_changed={editThreat.damage_description?.length > 0}
										/>
										<label for="edit-damage-description" class="input__label">Damage Description</label>
									</div>

									<div class="input">
										<input
											id="edit-mitigation-level"
											type="number"
											bind:value={editThreat.mitigation_level}
											class="input__text"
										/>
										<label for="edit-mitigation-level" class="input__label">Mitigation Level</label>
									</div>
									
									<label class="checkbox-label">
										<input
											type="checkbox"
											bind:checked={editThreat.disabled}
										/>
										Disabled
									</label>
								</div>

								<div class="form-section">
									<h3>STRIDE Classification</h3>
									<div class="stride-checkboxes">
										<label class="checkbox-label">
											<input
												type="checkbox"
												bind:checked={editThreat.spoofing}
											/>
											Spoofing
										</label>
										<label class="checkbox-label">
											<input
												type="checkbox"
												bind:checked={editThreat.tampering}
											/>
											Tampering
										</label>
										<label class="checkbox-label">
											<input
												type="checkbox"
												bind:checked={editThreat.repudiation}
											/>
											Repudiation
										</label>
										<label class="checkbox-label">
											<input
												type="checkbox"
												bind:checked={editThreat.information_disclosure}
											/>
											Information Disclosure
										</label>
										<label class="checkbox-label">
											<input
												type="checkbox"
												bind:checked={editThreat.denial_of_service}
											/>
											Denial of Service
										</label>
										<label class="checkbox-label">
											<input
												type="checkbox"
												bind:checked={editThreat.elevation_of_privilege}
											/>
											Elevation of Privilege
										</label>
									</div>
								</div>

								<div class="form-section">
									<h3>Related Cards</h3>
									<div class="card-search">
										<input
											id="card-search"
											type="text"
											bind:value={cardSearchQuery}
											oninput={(e) => searchCards(e.target.value)}
											class="input__text input__text_changed"
											placeholder="Search cards..."
										/>
										<label for="card-search" class="input__label">Search</label>
										{#if showCardDropdown && filteredCards.length > 0}
											<div class="card-dropdown">
												{#each filteredCards as card}
													<div class="card-option" onclick={() => toggleCard(card)}>
														<label class="checkbox-label" style="margin: 0;">
															<input
																type="checkbox"
																checked={selectedCardIds.has(card.id as any)}
																onchange={(e) => {
																	if (e.target.checked) {
																		selectedCardIds.add(card.id as any);
																	} else {
																		selectedCardIds.delete(card.id as any);
																	}
																	selectedCardIds = selectedCardIds;
																}}
															/>
															<div class="card-name">{card.name}</div>
														</label>
														<div class="card-description">{card.description}</div>
													</div>
												{/each}
											</div>
										{/if}
									</div>

									{#if selectedCardIds.size > 0}
										<div class="selected-cards">
											<h4>Selected Cards ({selectedCardIds.size})</h4>
											{#each Array.from(selectedCardIds) as cardId}
												{@const card = allCards.find(c => c.id === String(cardId))}
												{#if card}
													<div class="selected-card">
														{card.name}
														<button 
															type="button"
															class="remove-card"
															onclick={() => {
																selectedCardIds.delete(cardId);
																selectedCardIds = selectedCardIds;
															}}
														>
															×
														</button>
													</div>
												{/if}
											{/each}
										</div>
									{/if}
								</div>

								<div class="form-section">
									<h3>Scenario (Markdown)</h3>
									<div class="scenario-editor">
										<textarea
											id="scenario-textarea"
											bind:value={editThreat.scenario}
											class="scenario-textarea"
											placeholder="Enter scenario in Markdown format..."
										></textarea>
										<div class="scenario-preview">
											<div class="preview-label">Preview</div>
											<div class="scenario-preview-content">
												{@html marked(editThreat.scenario || '')}
											</div>
										</div>
									</div>
								</div>

								<div class="form-actions">
									<button
										type="button"
										class="button button_secondary"
										onclick={cancelEdit}
									>
										Cancel
									</button>
									<button
										type="button"
										class="button button_green"
										onclick={handleSave}
									>
										Save
									</button>
								</div>
							</div>
						</div>
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.back-link {
		display: inline-block;
		margin-bottom: 1rem;
		color: #0066cc;
		text-decoration: none;
		font-size: 14px;
	}

	.back-link:hover {
		text-decoration: underline;
	}

	.threat-detail-card {
		padding: 30px;
	}

	.card-header-actions {
		display: flex;
		gap: 10px;
		justify-content: flex-end;
		margin-bottom: 30px;
	}

	.detail-section {
		margin-bottom: 30px;
	}

	.detail-section h3 {
		font-size: 16px;
		font-weight: 600;
		margin-bottom: 15px;
		color: #333;
		border-bottom: 2px solid #f0f0f0;
		padding-bottom: 10px;
	}

	.detail-row {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
		gap: 20px;
		margin-bottom: 15px;
	}

	.detail-field {
		display: flex;
		flex-direction: column;
	}

	.detail-field.full {
		grid-column: 1 / -1;
	}

	.detail-field label {
		font-size: 12px;
		font-weight: 600;
		color: #666;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		margin-bottom: 6px;
	}

	.detail-field p {
		font-size: 14px;
		color: #333;
		margin: 0;
		word-break: break-word;
	}

	.stride-display {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 12px;
	}

	.stride-item {
		padding: 10px 12px;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-size: 13px;
		color: #666;
		background: #f9f9f9;
	}

	.stride-item.active {
		background: #d4edda;
		border-color: #28a745;
		color: #155724;
		font-weight: 500;
	}

	.cards-list {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
		gap: 12px;
	}

	.card-item {
		padding: 12px;
		border: 1px solid #ddd;
		border-radius: 4px;
		background: #f9f9f9;
	}

	.card-name {
		font-weight: 500;
		color: #333;
		font-size: 13px;
		margin-bottom: 4px;
	}

	.card-description {
		font-size: 12px;
		color: #666;
	}

	.scenario-content {
		padding: 15px;
		background: #f9f9f9;
		border: 1px solid #ddd;
		border-radius: 4px;
		line-height: 1.6;
	}

	:global(.scenario-content h1) {
		font-size: 20px;
		font-weight: bold;
		margin: 15px 0 10px 0;
	}

	:global(.scenario-content h2) {
		font-size: 16px;
		font-weight: bold;
		margin: 12px 0 8px 0;
	}

	:global(.scenario-content p) {
		margin: 8px 0;
	}

	:global(.scenario-content ul),
	:global(.scenario-content ol) {
		margin: 8px 0 8px 20px;
	}

	:global(.scenario-content code) {
		background: #e0e0e0;
		padding: 2px 6px;
		border-radius: 3px;
		font-size: 12px;
	}

	.edit-form {
		display: flex;
		flex-direction: column;
		gap: 30px;
	}

	.form-section {
		padding: 20px;
		background: #f9f9f9;
		border: 1px solid #eee;
		border-radius: 4px;
	}

	.form-section h3 {
		margin-top: 0;
		margin-bottom: 20px;
		font-size: 14px;
		font-weight: 600;
		color: #333;
	}

	.form-section .input {
		margin-bottom: 15px;
	}

	.form-section .input:last-child {
		margin-bottom: 0;
	}

	.card-search {
		position: relative;
		margin-bottom: 15px;
	}

	.card-dropdown {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		background: white;
		border: 1px solid #ddd;
		border-top: none;
		border-radius: 0 0 4px 4px;
		max-height: 150px;
		overflow-y: auto;
		z-index: 10;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
	}

	.card-option {
		padding: 10px 12px;
		cursor: pointer;
		border-bottom: 1px solid #f0f0f0;
	}

	.card-option:hover {
		background-color: #f5f5f5;
	}

	.card-option .card-name {
		font-weight: 500;
		color: #333;
		font-size: 13px;
	}

	.card-option .card-description {
		font-size: 12px;
		color: #666;
		margin-top: 4px;
	}

	.selected-cards {
		margin-top: 15px;
		padding: 12px;
		background: #e8f4f8;
		border: 1px solid #0066cc;
		border-radius: 4px;
	}

	.selected-cards h4 {
		margin: 0 0 10px 0;
		font-size: 13px;
		color: #0066cc;
	}

	.selected-card {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: white;
		border: 1px solid #0066cc;
		border-radius: 3px;
		padding: 4px 8px;
		font-size: 12px;
		color: #0066cc;
		margin-right: 8px;
		margin-bottom: 8px;
	}

	.remove-card {
		background: none;
		border: none;
		color: #0066cc;
		cursor: pointer;
		font-size: 14px;
		padding: 0;
		line-height: 1;
		display: flex;
		align-items: center;
	}

	.remove-card:hover {
		color: #004499;
	}

	.scenario-editor {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 15px;
		height: 300px;
	}

	.scenario-textarea {
		padding: 10px;
		border: 1px solid #ddd;
		border-radius: 4px;
		font-family: 'Monaco', 'Courier New', monospace;
		font-size: 13px;
		resize: none;
		width: 100%;
		height: 100%;
	}

	.scenario-textarea:focus {
		outline: none;
		border-color: #999;
	}

	.scenario-preview {
		display: flex;
		flex-direction: column;
		border: 1px solid #ddd;
		border-radius: 4px;
		background: #f9f9f9;
		overflow: hidden;
	}

	.preview-label {
		padding: 8px 10px;
		font-size: 11px;
		font-weight: bold;
		color: #666;
		border-bottom: 1px solid #ddd;
		background: #f0f0f0;
	}

	.scenario-preview-content {
		flex: 1;
		overflow-y: auto;
		padding: 10px;
		font-size: 13px;
		line-height: 1.5;
	}

	:global(.scenario-preview-content h1) {
		font-size: 18px;
		font-weight: bold;
		margin: 10px 0 8px 0;
	}

	:global(.scenario-preview-content h2) {
		font-size: 15px;
		font-weight: bold;
		margin: 8px 0 6px 0;
	}

	:global(.scenario-preview-content p) {
		margin: 6px 0;
	}

	:global(.scenario-preview-content ul),
	:global(.scenario-preview-content ol) {
		margin: 6px 0 6px 15px;
	}

	:global(.scenario-preview-content li) {
		margin: 2px 0;
	}

	.stride-checkboxes {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}

	.checkbox-label {
		display: flex;
		align-items: center;
		gap: 8px;
		cursor: pointer;
		font-size: 13px;
		margin: 0;
	}

	.checkbox-label input[type="checkbox"] {
		cursor: pointer;
		width: 16px;
		height: 16px;
	}

	.form-actions {
		display: flex;
		gap: 10px;
		justify-content: flex-end;
		padding-top: 20px;
		border-top: 1px solid #eee;
	}
</style>
