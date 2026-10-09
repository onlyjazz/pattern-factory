<script lang="ts">
	import CloseSendResult from './CloseSendResult.svelte';
	import type { StartExperimentResult } from '$lib/closeSend';
	import type { Experiment } from '$lib/types/models';

	export let experiment: Experiment | null = null;
	export let sending = false;
	export let sendError: string | null = null;
	export let sendResult: StartExperimentResult | null = null;
	export let onSend: (() => void) | null = null;

	$: hasProducts = (experiment?.product_ids?.length ?? 0) > 0;
	$: hasSteps = (experiment?.steps?.length ?? 0) > 0;
	$: canSend = hasProducts && hasSteps;
</script>

<div class="detail-section">
	<h3>Send to Close</h3>
	<p class="help-text">
		Push this experiment's products, orgs and people to Close CRM. Re-running refreshes each
		Close company's custom fields.
	</p>
	{#if !hasSteps}
		<p class="help-text">Add at least one step on the edit page before sending.</p>
	{:else if !hasProducts}
		<p class="help-text">Assign at least one product on the edit page before sending.</p>
	{/if}
	<div class="form-footer">
		<button
			type="button"
			class="button button_green"
			onclick={() => onSend?.()}
			disabled={sending || !canSend}
		>
			{sending ? 'Sending...' : 'Send to Close'}
		</button>
	</div>
	{#if sendError}
		<div class="message message-error error-margin-v">Error: {sendError}</div>
	{/if}
	<CloseSendResult result={sendResult} />
</div>
