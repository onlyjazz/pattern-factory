<script lang="ts">
	import type { Experiment } from '$lib/types/models';
	import { ARM_OPTIONS, type ExperimentArm } from '$lib/experiments';
	import { API_BASE } from '$lib/config';

	export let open = false;
	export let onClose: () => void = () => {};
	export let onCreated: (experiment: Experiment) => void = () => {};

	let name = '';
	let description = '';
	let arm: ExperimentArm = 'social';
	let saving = false;
	let error: string | null = null;

	function reset() {
		name = '';
		description = '';
		arm = 'social';
		saving = false;
		error = null;
	}

	function close() {
		reset();
		onClose();
	}

	async function handleCreate() {
		if (!name.trim()) {
			error = 'Name is required';
			return;
		}
		try {
			saving = true;
			error = null;
			const response = await fetch(`${API_BASE}/experiments`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: name.trim(),
					description: description.trim() || null,
					arm,
					email_header_status: 'draft',
					steps: [],
					product_ids: []
				})
			});
			if (!response.ok) throw new Error('Failed to create experiment');
			const created: Experiment = await response.json();
			reset();
			onCreated(created);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create experiment';
			saving = false;
		}
	}
</script>

{#if open}
	<div
		class="modal-overlay"
		role="presentation"
		onclick={close}
		onkeydown={(e) => e.key === 'Escape' && close()}
	>
		<div
			class="modal-content"
			role="dialog"
			aria-labelledby="add-experiment-title"
			tabindex="0"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<div class="modal-header">
				<h2 id="add-experiment-title" class="heading heading_2">Add Experiment</h2>
				<button type="button" class="modal-close" onclick={close} title="Close">×</button>
			</div>
			<div class="modal-body">
				{#if error}
					<div class="message message-error error-margin">Error: {error}</div>
				{/if}
				<form onsubmit={(e) => { e.preventDefault(); handleCreate(); }}>
					<div class="input">
						<input
							id="add-experiment-name"
							type="text"
							bind:value={name}
							class="input__text"
							class:input__text_changed={name.length > 0}
							required
						/>
						<label for="add-experiment-name" class="input__label">Name</label>
					</div>
					<div class="input">
						<textarea
							id="add-experiment-description"
							bind:value={description}
							class="input__text"
							class:input__text_changed={description.length > 0}
						></textarea>
						<label for="add-experiment-description" class="input__label">Description</label>
					</div>
					<div class="input input_select">
						<select id="add-experiment-arm" bind:value={arm} class="input__text" class:input__text_changed={true}>
							{#each ARM_OPTIONS as option}
								<option value={option.value}>{option.label}</option>
							{/each}
						</select>
						<label for="add-experiment-arm" class="input__label">Arm</label>
					</div>
					<div class="modal-footer">
						<button type="button" class="button button_secondary" onclick={close}>Cancel</button>
						<button type="submit" class="button button_green" disabled={saving}>
							{saving ? 'Saving...' : 'Save'}
						</button>
					</div>
				</form>
			</div>
		</div>
	</div>
{/if}
