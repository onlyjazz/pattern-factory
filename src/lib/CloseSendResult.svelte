<script lang="ts">
	import type { StartExperimentResult } from '$lib/closeSend';

	export let result: StartExperimentResult | null = null;
</script>

{#if result}
	<div class="message {result.failed === 0 ? 'message-success' : 'message-error'} error-margin-v">
		Sent to Close: {result.companies}
		{result.companies === 1 ? 'company' : 'companies'}, {result.contacts}
		{result.contacts === 1 ? 'contact' : 'contacts'}.
		{#if result.failed > 0}
			{result.failed} of {result.success + result.failed} products failed.
		{/if}
	</div>
	{#if result.smartViewError}
		<div class="message message-error error-margin-v">Smart view: {result.smartViewError}</div>
	{/if}
	{#if result.errors.length > 0}
		<ul class="paragraph">
			{#each result.errors as err}
				<li>{err}</li>
			{/each}
		</ul>
	{/if}
{/if}
