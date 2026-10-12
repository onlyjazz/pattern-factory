<script lang="ts">
	import CloseSendResult from './CloseSendResult.svelte';
	import type { StartExperimentResult } from '$lib/closeSend';

	export let sendCount = 0;
	export let hasSteps = false;
	export let sending = false;
	export let sendError: string | null = null;
	export let sendResult: StartExperimentResult | null = null;
	export let onSend: (() => void) | null = null;

	$: canSend = hasSteps && sendCount > 0;
</script>

<div class="detail-section">
	<h3>Send to Close</h3>
	<p class="help-text">
		Push this experiment's products, orgs and people to Close CRM. Re-running refreshes each
		Close company's custom fields.
	</p>
	{#if !hasSteps}
		<p class="help-text">Add at least one step on the edit page before sending.</p>
	{:else if sendCount === 0}
		<p class="help-text">Select products on the Products page (or assign them here) before sending.</p>
	{:else}
		<p class="help-text">{sendCount} {sendCount === 1 ? 'product' : 'products'} will be sent to Close.</p>
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
