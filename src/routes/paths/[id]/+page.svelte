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
	let newNodeEntry = { id: '', type: 'assumption', label: '', optionalityCollapses: false };
	let newEdgeEntry = { from_node: '', to_node: '', reason: '' };

	const nodeTypes = ['assumption', 'decision', 'state'];
	const apiBase = 'http://localhost:8000';

	onMount(async () => {
		try {
			const pathId = $page.params.id;
			const response = await fetch(`${apiBase}/paths/${pathId}`);
			if (!response.ok) throw new Error('Failed to fetch path');
			path = await response.json();
			
			if (path?.yaml) {
				nodes = [...(path.yaml.nodes || [])];
				edges = [...(path.yaml.edges || [])];
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
				optionality: newNodeEntry.optionalityCollapses
					? { collapses: true, reason: '' }
					: undefined
			}
		];
		// Reset entry form
		newNodeEntry = { id: '', type: 'assumption', label: '', optionalityCollapses: false };
	}

	function removeNode(index: number) {
		const removedNodeId = nodes[index].id;
		nodes = nodes.filter((_, i) => i !== index);
		// Remove edges referencing this node
		edges = edges.filter(e => e.from_node !== removedNodeId && e.to_node !== removedNodeId);
	}

	function addEdge() {
		if (!newEdgeEntry.from_node || !newEdgeEntry.to_node || !newEdgeEntry.reason.trim()) return;
		edges = [...edges, { from_node: newEdgeEntry.from_node, to_node: newEdgeEntry.to_node, reason: newEdgeEntry.reason }];
		// Reset entry form
		newEdgeEntry = { from_node: '', to_node: '', reason: '' };
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

		// Validate nodes
		const nodeIds = nodes.map(n => n.id).filter(id => id && id.trim());
		if (nodeIds.length === 0) {
			error = 'At least one node with an ID is required';
			return;
		}

		// Check for duplicate node IDs
		if (new Set(nodeIds).size !== nodeIds.length) {
			error = 'Node IDs must be unique';
			return;
		}

		// No need to validate - entry form enforces valid data before adding
		// All nodes and edges should be complete by this point
		const completeNodes = nodes;
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
					edges: completeEdges
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

	function updateNodeOptionalityCollapse(index: number, value: boolean) {
		nodes[index] = {
			...nodes[index],
			optionality: value 
				? { collapses: true, reason: nodes[index].optionality?.reason || '' }
				: undefined
		};
		nodes = nodes;
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
									<td class="col-options">
										<input type="checkbox" bind:checked={newNodeEntry.optionalityCollapses} class="table-checkbox" />
									</td>
								</tr>
								<!-- Display rows -->
								{#each nodes as node, i (i)}
									<tr class="display-row">
										<td class="col-action">
											<button class="button-icon button-delete" onclick={() => removeNode(i)} title="Delete node">−</button>
										</td>
										<td class="col-id">{node.id}</td>
										<td class="col-type">{node.type}</td>
										<td class="col-label">{node.label}</td>
										<td class="col-options">{node.optionality?.collapses ? '⚠️' : ''}</td>
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

		<!-- SAVE BUTTON -->
		<div class="grid-row">
			<div class="grid-col grid-col_24">
				<div class="card">
					<div class="button-group">
						<a href="/paths" class="button button_secondary">Back to Paths</a>
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
		width: 120px;
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
</style>
