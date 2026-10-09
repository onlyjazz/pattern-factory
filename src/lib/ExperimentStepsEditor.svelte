<script lang="ts">
	import type { ExperimentStep } from '$lib/types/models';

	export let steps: ExperimentStep[] = [];

	const channelOptions: ExperimentStep['channel'][] = ['buffer', 'email'];

	function addStep() {
		steps = [
			...steps,
			{ position: steps.length + 1, channel: 'email', content_id: null, content_rev: null }
		];
	}

	function removeStep(index: number) {
		steps = steps
			.filter((_, i) => i !== index)
			.map((step, i) => ({ ...step, position: i + 1 }));
	}
</script>

<div class="steps-editor">
	{#if steps.length === 0}
		<p class="help-text">No steps yet. Add at least one channel.</p>
	{/if}
	{#each steps as step, i (i)}
		<div class="steps-editor__row">
			<span class="steps-editor__position">{i + 1}</span>
			<div class="input input_select steps-editor__field">
				<select
					id={`step-channel-${i}`}
					bind:value={step.channel}
					class="input__text"
					class:input__text_changed={true}
				>
					{#each channelOptions as channel}
						<option value={channel}>{channel}</option>
					{/each}
				</select>
				<label class="input__label" for={`step-channel-${i}`}>Channel</label>
			</div>
			<div class="input steps-editor__field">
				<input
					id={`step-content-id-${i}`}
					type="text"
					bind:value={step.content_id}
					class="input__text"
					class:input__text_changed={!!step.content_id}
				/>
				<label class="input__label" for={`step-content-id-${i}`}>Content ID</label>
			</div>
			<div class="input steps-editor__field">
				<input
					id={`step-content-rev-${i}`}
					type="text"
					bind:value={step.content_rev}
					class="input__text"
					class:input__text_changed={!!step.content_rev}
				/>
				<label class="input__label" for={`step-content-rev-${i}`}>Content Rev</label>
			</div>
			<button
				type="button"
				class="button button_small"
				onclick={() => removeStep(i)}
				title="Remove step"
			>
				−
			</button>
		</div>
	{/each}
	<div class="steps-editor__actions">
		<button type="button" class="button button_blue" onclick={addStep}>Add step</button>
	</div>
</div>
