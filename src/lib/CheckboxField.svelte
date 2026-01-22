<script lang="ts">
	export let id: string;
	export let checked: boolean = false;
	export let label: string;
	export let description: string = '';
	export let disabled: boolean = false;
</script>

<div class="checkbox-field">
	<div style="display: flex; align-items: flex-start;">
		<input
			type="checkbox"
			{id}
			bind:checked
			class="checkbox-input"
			{disabled}
		/>
		<div class="checkbox-label">
			<label for={id} class="checkbox-label-text">{label}</label>
			{#if description}
				<span class="checkbox-label-description">{description}</span>
			{/if}
		</div>
	</div>
</div>
