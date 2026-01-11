<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import type { Path, PathNode, PathEdge } from '$lib/db';

	let path: Path | null = null;
	let loading = true;
	let error: string | null = null;
	let isSaving = false;

	let nodes: PathNode[] = [];
	let edges: PathEdge[] = [];
	let youAreHere: number | null = null;
	let newNodeEntry = { id: '', type: 'assumption', label: '', optionalityCollapses: 'f' };
	let newEdgeEntry = { from_node: '', to_node: '', reason: '' };
	
	// Optionality modal state
	let showOptionalityModal = false;
	let editingNodeIndex: number | null = null;
	let currentOptionality = { collapses: false, reason: '', irreversible: false };
	let modalPosition = { x: 0, y: 0 };
	let isDragging = false;
	let dragOffset = { x: 0, y: 0 };

	// Empty nodes confirmation modal state
	let showEmptyNodesModal = false;
	let pendingSave = false;

	// Causal flow error modal state
	let showCausalFlowErrorModal = false;

	const nodeTypes = ['assumption', 'decision', 'state'];
	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const pathId = $page.params.id;
			const response = await fetch(`${apiBase}/paths/${pathId}`);
			if (!response.ok) throw new Error('Failed to fetch path');
			path = await response.json();
			
		if (path?.yaml) {
			nodes = [...(path.yaml.nodes || [])].map((node, index) => ({
				...node,
				serial: node.serial || index + 1
			}));
			edges = [...(path.yaml.edges || [])];
			youAreHere = path.yaml.youAreHere || null;
		}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unknown error';
		} finally {
			loading = false;
		}
	});

	function addNode() {
		if (!newNodeEntry.id.trim() || !newNodeEntry.label.trim()) return;
		nodes = [
			...nodes,
			{
				id: newNodeEntry.id,
				type: newNodeEntry.type,
				label: newNodeEntry.label,
				serial: nodes.length + 1,
				optionality: newNodeEntry.optionalityCollapses === 't'
					? { collapses: true, reason: '' }
					: undefined
			}
		];
		// Reset entry form
		newNodeEntry = { id: '', type: 'assumption', label: '', optionalityCollapses: 'f' };
	}

	function removeNode(index: number) {
		const removedNodeId = nodes[index].id;
		const removedSerial = nodes[index].serial;
		nodes = nodes.filter((_, i) => i !== index);
		// Renumber serial positions
		nodes = nodes.map((node, i) => ({ ...node, serial: i + 1 }));
		// Clear youAreHere if deleted node was selected
		if (youAreHere === removedSerial) {
			youAreHere = null;
		}
		// Remove edges referencing this node
		edges = edges.filter(e => e.from_node !== removedNodeId && e.to_node !== removedNodeId);
	}

	function selectNode(serial: number | undefined) {
		youAreHere = serial || null;
	}

	function addEdge() {
		if (!newEdgeEntry.from_node || !newEdgeEntry.to_node || !newEdgeEntry.reason.trim()) return;
		
		// Validate causal flow: from_node serial must be < to_node serial
		const fromNode = nodes.find(n => n.id === newEdgeEntry.from_node);
		const toNode = nodes.find(n => n.id === newEdgeEntry.to_node);
		
		if (!fromNode || !toNode) return;
		if ((fromNode.serial || 0) >= (toNode.serial || 0)) {
			showCausalFlowErrorModal = true;
			return;
		}
		
		edges = [...edges, { from_node: newEdgeEntry.from_node, to_node: newEdgeEntry.to_node, reason: newEdgeEntry.reason }];
		// Reset entry form
		newEdgeEntry = { from_node: '', to_node: '', reason: '' };
	}

	function closeCausalFlowErrorModal() {
		showCausalFlowErrorModal = false;
	}

	function removeEdge(index: number) {
		edges = edges.filter((_, i) => i !== index);
	}

	function getValidNodeIds(): string[] {
		return nodes.map(n => n.id).filter(id => id && id.trim());
	}

	function isEdgeValid(edge: PathEdge): boolean {
		const validIds = getValidNodeIds();
		return validIds.includes(edge.from_node) && validIds.includes(edge.to_node) && edge.reason.trim() !== '';
	}

	async function handleSave() {
		if (!path) return;

		// Validate
		if (!path.name || !path.name.trim()) {
			error = 'Path name is required';
			return;
		}


		// Confirm if no nodes
		if (nodes.length === 0) {
			showEmptyNodesModal = true;
			pendingSave = true;
			return;
		}

		await performSave();
	}

	async function performSave() {
		if (!path) return;

		// Ensure serial positions are set for all nodes
		const completeNodes = nodes.map((node, index) => ({
			...node,
			serial: node.serial || index + 1
		}));
		const completeEdges = edges;

		isSaving = true;
		try {
			const response = await fetch(`${apiBase}/paths/${path.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: path.name,
					description: path.description,
					nodes: completeNodes,
					edges: completeEdges,
					youAreHere: youAreHere
				})
			});

			if (!response.ok) throw new Error('Failed to save path');
			const updated = await response.json();
			path = updated;
			if (updated.yaml) {
				nodes = [...updated.yaml.nodes];
				edges = [...updated.yaml.edges];
			}
			error = null;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save path';
		} finally {
			isSaving = false;
		}
	}

	function openOptionalityModal(index: number) {
		editingNodeIndex = index;
		const node = nodes[index];
		if (node.optionality) {
			currentOptionality = { ...node.optionality };
		} else {
			currentOptionality = { collapses: false, reason: '', irreversible: false };
		}
		showOptionalityModal = true;
	}
	
	function closeOptionalityModal() {
		showOptionalityModal = false;
		editingNodeIndex = null;
		currentOptionality = { collapses: false, reason: '', irreversible: false };
	}

	function startDrag(e: MouseEvent) {
		if (e.target === e.currentTarget || (e.target as HTMLElement).classList.contains('modal-header')) {
			isDragging = true;
			dragOffset = {
				x: e.clientX - modalPosition.x,
				y: e.clientY - modalPosition.y
			};
		}
	}

	function onDrag(e: MouseEvent) {
		if (!isDragging) return;
		modalPosition = {
			x: e.clientX - dragOffset.x,
			y: e.clientY - dragOffset.y
		};
	}

	function stopDrag() {
		isDragging = false;
	}
	
	function saveOptionality() {
		if (editingNodeIndex !== null) {
			if (currentOptionality.collapses || currentOptionality.reason || currentOptionality.irreversible) {
				// Always replace with form data only - collapses, reason, irreversible
				nodes[editingNodeIndex].optionality = {
					collapses: currentOptionality.collapses,
					reason: currentOptionality.reason,
					irreversible: currentOptionality.irreversible
				};
			} else {
				nodes[editingNodeIndex].optionality = undefined;
			}
			nodes = nodes;
		}
		closeOptionalityModal();
	}

	function closeEmptyNodesModal() {
		showEmptyNodesModal = false;
		pendingSave = false;
	}

	async function confirmEmptyNodesSave() {
		closeEmptyNodesModal();
		await performSave();
	}
</script>

<div id="application-content-area">
	<div class="page-title">
		{#if path}
			<h1 class="heading heading_1">{path.name}</h1>
		{/if}
	</div>

	{#if loading}
		<div class="message">Loading path...</div>
	{:else if error}
		<div class="message message-error">Error: {error}</div>
	{:else if !path}
		<div class="message">Path not found</div>
	{:else}
		<div class="grid-row">
			<!-- PATH INFO -->
			<div class="grid-col grid-col_24">
				<div class="card">
					<div class="input">
						<input
							id="path-name"
							type="text"
							bind:value={path.name}
							class="input__text"
							class:input__text_changed={path.name?.length > 0}
							required
						/>
						<label for="path-name" class="input__label">Path Name</label>
					</div>

					<div class="input">
						<input
							id="path-description"
							type="text"
							bind:value={path.description}
							class="input__text"
							class:input__text_changed={path.description?.length > 0}
						/>
						<label for="path-description" class="input__label">Description</label>
					</div>
				</div>
			</div>
		</div>

		<div class="grid-row">
			<!-- LEFT PANEL: NODES -->
			<div class="grid-col grid-col_12">
				<div class="card">
					<h3 class="heading heading_3">Nodes</h3>
					<div class="table-container">
						<table class="data-table">
							<thead>
								<tr>
									<th class="col-action"></th>
									<th class="col-id">ID</th>
									<th class="col-type">Type</th>
									<th class="col-label">Label</th>
									<th class="col-options">Optionality</th>
								</tr>
							</thead>
							<tbody>
								<!-- Data entry row -->
								<tr class="entry-row">
									<td class="col-action">
										<button class="button-icon" onclick={addNode} title="Add node">+</button>
									</td>
									<td class="col-id"><input type="text" bind:value={newNodeEntry.id} class="table-input" placeholder="" /></td>
									<td class="col-type">
										<select bind:value={newNodeEntry.type} class="table-select">
											{#each nodeTypes as type}
												<option value={type}>{type}</option>
											{/each}
										</select>
									</td>
									<td class="col-label"><input type="text" bind:value={newNodeEntry.label} class="table-input" placeholder="" /></td>
									<td class="col-options"></td>
								</tr>
								<!-- Display rows -->
								{#each nodes as node, i (i)}
									<tr class="display-row" class:selected-node={youAreHere === node.serial} onclick={() => selectNode(node.serial)}>
										<td class="col-action">
											<button class="button-icon button-delete" onclick={(e) => { e.stopPropagation(); removeNode(i); }} title="Delete node">−</button>
										</td>
										<td class="col-id">{node.id}</td>
										<td class="col-type">{node.type}</td>
										<td class="col-label">{node.label}</td>
										<td class="col-options">
											<button class="button-icon" onclick={(e) => { e.stopPropagation(); openOptionalityModal(i); }} title="Edit optionality">
												{node.optionality?.collapses ? '⚠️' : '○'}
											</button>
										</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			</div>

			<!-- RIGHT PANEL: EDGES -->
			<div class="grid-col grid-col_12">
				<div class="card">
					<h3 class="heading heading_3">Edges</h3>
					<div class="table-container">
						<table class="data-table">
							<thead>
								<tr>
									<th class="col-action"></th>
									<th class="col-from">From</th>
									<th class="col-to">To</th>
									<th class="col-reason">Reason</th>
								</tr>
							</thead>
							<tbody>
								<!-- Data entry row -->
								<tr class="entry-row">
									<td class="col-action">
										<button class="button-icon" onclick={addEdge} title="Add edge">+</button>
									</td>
									<td class="col-from">
										<select bind:value={newEdgeEntry.from_node} class="table-select">
											<option value="">Node</option>
											{#each getValidNodeIds() as nodeId}
												<option value={nodeId}>{nodeId}</option>
											{/each}
										</select>
									</td>
									<td class="col-to">
										<select bind:value={newEdgeEntry.to_node} class="table-select">
											<option value="">Node</option>
											{#each getValidNodeIds() as nodeId}
												<option value={nodeId}>{nodeId}</option>
											{/each}
										</select>
									</td>
									<td class="col-reason"><input type="text" bind:value={newEdgeEntry.reason} class="table-input" placeholder="" /></td>
								</tr>
								<!-- Display rows -->
								{#each edges as edge, i (i)}
									<tr class="display-row">
										<td class="col-action">
											<button class="button-icon button-delete" onclick={() => removeEdge(i)} title="Delete edge">−</button>
										</td>
										<td class="col-from">{edge.from_node}</td>
										<td class="col-to">{edge.to_node}</td>
										<td class="col-reason">{edge.reason}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</div>

		<!-- OPTIONALITY MODAL -->
		{#if showOptionalityModal}
			<div class="modal-overlay" onmouseup={stopDrag} onmousemove={onDrag} onclick={closeOptionalityModal}>
				<div
					class="modal-content"
					role="dialog"
					aria-labelledby="optionality-modal-title"
					onclick={(e) => e.stopPropagation()}
					style="transform: translate({modalPosition.x}px, {modalPosition.y}px);"
				>
					<div class="modal-header" onmousedown={startDrag}>
						<h2 id="optionality-modal-title" class="heading heading_2">Optionality</h2>
						<button class="modal-close" onclick={closeOptionalityModal} title="Close">×</button>
					</div>
					<div class="modal-body">
						<div class="checkbox-item">
							<input type="checkbox" id="collapses-check" bind:checked={currentOptionality.collapses} />
							<label for="collapses-check">Optionality Collapses</label>
						</div>
						<div class="input modal-input">
							<input
								id="optionality-reason"
								type="text"
								bind:value={currentOptionality.reason}
								class="input__text"
								class:input__text_changed={currentOptionality.reason?.length > 0}
								placeholder=""
							/>
							<label for="optionality-reason" class="input__label">Reason</label>
						</div>
						<div class="checkbox-item checkbox-item-reversible">
							<input type="checkbox" id="irreversible-check" bind:checked={currentOptionality.irreversible} />
							<label for="irreversible-check">Irreversible</label>
						</div>
						{#if currentOptionality.irreversible}
							<div class="reversible-note">After this point, fixes have personal, regulatory, commercial, and reputational costs.</div>
						{/if}
					</div>
					<div class="modal-footer">
						<button type="button" class="button button_secondary" onclick={closeOptionalityModal}>
							Cancel
						</button>
						<button type="button" class="button button_green" onclick={saveOptionality}>
							Save
						</button>
					</div>
				</div>
			</div>
		{/if}

		<!-- EMPTY NODES CONFIRMATION MODAL -->
		{#if showEmptyNodesModal}
			<div class="modal-overlay" onclick={closeEmptyNodesModal}>
				<div class="modal-content" role="dialog" aria-labelledby="empty-nodes-modal-title" onclick={(e) => e.stopPropagation()}>
					<div class="modal-header">
						<h2 id="empty-nodes-modal-title" class="heading heading_2">Save empty path?</h2>
						<button class="modal-close" onclick={closeEmptyNodesModal} title="Close">×</button>
					</div>
					<div class="modal-footer">
						<button type="button" class="button button_secondary" onclick={closeEmptyNodesModal}>
							Cancel
						</button>
						<button type="button" class="button button_green" onclick={confirmEmptyNodesSave}>
							Save
						</button>
					</div>
				</div>
			</div>
		{/if}

		<!-- CAUSAL FLOW ERROR MODAL -->
		{#if showCausalFlowErrorModal}
			<div class="modal-overlay" onclick={closeCausalFlowErrorModal}>
				<div class="modal-content" role="dialog" aria-labelledby="causal-flow-error-title" onclick={(e) => e.stopPropagation()}>
					<div class="modal-header">
						<h2 id="causal-flow-error-title" class="heading heading_2">From node after To node</h2>
						<button class="modal-close" onclick={closeCausalFlowErrorModal} title="Close">×</button>
					</div>
					<div class="modal-footer">
						<button type="button" class="button button_green" onclick={closeCausalFlowErrorModal}>
							OK
						</button>
					</div>
				</div>
			</div>
		{/if}

		<!-- SAVE BUTTON -->
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="card">
					<div class="button-group">
						<button
							class="button button_green"
							onclick={handleSave}
							disabled={isSaving}
						>
							{isSaving ? 'Saving...' : 'Save Path'}
						</button>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.table-container {
		overflow-x: hidden;
		overflow-y: visible;
		margin-bottom: 1rem;
	}

	.data-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.9rem;
	}

	.data-table thead {
		background: #f5f5f5;
		border-bottom: 2px solid #ddd;
	}

	.data-table th {
		padding: 0.5rem 0.25rem;
		text-align: left;
		font-weight: 600;
		color: #333;
	}

	.data-table tbody tr {
		border-bottom: 1px solid #eee;
	}

	.data-table tbody tr.entry-row {
		background: #fafafa;
	}

	.data-table tbody tr.display-row {
		background: white;
	}

	.data-table tbody tr.display-row:hover {
		background: #f9f9f9;
		cursor: pointer;
	}

	.data-table tbody tr.display-row.selected-node {
		background: #e8f5e9;
	}

	.data-table td {
		padding: 0.5rem 0.25rem;
		vertical-align: middle;
	}

	.col-action {
		width: 20px;
		text-align: center;
		padding: 0.75rem 0.25rem !important;
	}

	.col-id {
		width: 55px;
		font-size: 0.8rem;
	}

	.col-type {
		width: 130px;
		padding-left: 8px !important;
		font-size: 0.8rem;
	}

	.col-label {
		flex: 1;
		min-width: 180px;
		padding-left: 8px !important;
		font-size: 0.8rem;
	}

	.col-options {
		width: 80px;
		text-align: center;
		padding-left: 20px !important;
		color: red !important;
		font-size: 0.8rem;
	}

	.col-from {
		width: 55px;
		font-size: 0.8rem;
	}

	.col-to {
		width: 55px;
		font-size: 0.8rem;
	}

	.col-reason {
		width: 115px;
		max-width: 115px;
		word-wrap: break-word;
		overflow-wrap: break-word;
		font-size: 0.8rem;
	}

	.table-input {
		width: 100%;
		padding: 0.375rem 0.25rem;
		border: 1px solid #ccc;
		border-radius: 3px;
		font-size: 0.8rem;
		font-family: inherit;
		box-sizing: border-box;
	}

	.table-input:focus {
		outline: none;
		border-color: #1976d2;
		box-shadow: 0 0 4px rgba(25, 118, 210, 0.2);
	}

	.table-select {
		width: 100%;
		padding: 0.375rem 0.25rem;
		border: 1px solid #ccc;
		border-radius: 3px;
		font-size: 0.8rem;
		font-family: inherit;
		cursor: pointer;
		box-sizing: border-box;
	}

	.table-select:focus {
		outline: none;
		border-color: #1976d2;
		box-shadow: 0 0 4px rgba(25, 118, 210, 0.2);
	}

	.table-checkbox {
		width: 18px;
		height: 18px;
		cursor: pointer;
		border: 1px solid #ccc;
		border-radius: 3px;
		box-sizing: border-box;
	}

	.button-icon {
		background: none;
		border: none;
		padding: 0.25rem 0.15rem;
		margin: 0;
		cursor: pointer;
		font-size: 0.8rem;
		color: #2196f3;
		font-weight: bold;
		line-height: 1;
	}

	.button-icon:hover {
		color: #1976d2;
	}

	.button-icon.button-delete {
		color: #d32f2f;
	}

	.button-icon.button-delete:hover {
		color: #b71c1c;
	}

	.button-group {
		display: flex;
		gap: 1rem;
		justify-content: flex-end;
	}

	.button-group a {
		text-decoration: none;
	}

	:global(.modal-overlay) {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}

	:global(.modal-content) {
		background: white;
		border-radius: 8px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		max-width: 500px;
		width: 90%;
		max-height: 80vh;
		overflow-y: auto;
		position: fixed;
		transition: none;
	}

	:global(.modal-header) {
		cursor: grab;
		user-select: none;
	}

	:global(.modal-header:active) {
		cursor: grabbing;
	}

	:global(.modal-header) {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 20px;
		border-bottom: 1px solid #eee;
	}

	:global(.modal-close) {
		background: none;
		border: none;
		font-size: 24px;
		cursor: pointer;
		color: #666;
		padding: 0;
		width: 30px;
		height: 30px;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	:global(.modal-close:hover) {
		color: #333;
	}

	:global(.modal-body) {
		padding: 20px;
	}

	:global(.modal-body form) {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	:global(.modal-footer) {
		display: flex;
		gap: 10px;
		justify-content: flex-end;
		margin-top: 20px;
		padding: 20px;
		border-top: 1px solid #eee;
	}

	:global(.checkbox-item) {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	:global(.checkbox-item input[type="checkbox"]) {
		cursor: pointer;
	}

	:global(.modal-body) {
		font-size: 0.8em;
	}

	:global(.modal-header) {
		font-size: 0.8em;
	}

	.modal-input {
		margin: 1.5rem 0 !important;
	}

	.checkbox-item-reversible {
		margin-top: 1.5rem;
	}

	.reversible-note {
		font-size: 0.75em;
		color: #666;
		margin-top: 0.75rem;
		font-style: italic;
		line-height: 1.4;
	}
</style>
