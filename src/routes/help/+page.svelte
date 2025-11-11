<script lang="ts">
	// You could later connect a form to an API endpoint if needed
	let name = '';
	let email = '';
	let message = '';
	let submitted = false;

	function submitForm() {
		if (name && email && message) {
			console.log({ name, email, message });
			submitted = true;
		}
	}
</script>

<div class="page-title">
	<h1 class="heading_1">Help & Support</h1>
</div>

<div class="card p-5 max-w-2xl mx-auto">
	{#if submitted}
		<div class="text-green-600 text-lg font-semibold">
			✅ Your message has been submitted. We'll get back to you shortly.
		</div>
	{:else}
		<p class="mb-4 text-gray-700">Having trouble with Pattern Factory? Fill out the form below and our team will get in touch.</p>
		<form on:submit|preventDefault={submitForm} class="grid gap-4">
			<div>
				<label class="block mb-1 font-semibold">Name</label>
				<input bind:value={name} class="input__text w-full" required />
			</div>

			<div>
				<label class="block mb-1 font-semibold">Email</label>
				<input type="email" bind:value={email} class="input__text w-full" required />
			</div>

			<div>
				<label class="block mb-1 font-semibold">Message</label>
				<textarea bind:value={message} class="input__text w-full" rows="5" required></textarea>
			</div>

			<button type="submit" class="button button_green mt-2 w-full">
				Submit
			</button>
		</form>
	{/if}
</div>

<style>
	.page-title {
		text-align: center;
		margin-top: 2rem;
		margin-bottom: 1rem;
	}
</style>
