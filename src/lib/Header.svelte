<script>
	import { page } from '$app/stores';
	import { globalSearch } from '$lib/searchStore';
	
	export let onChatClick = () => {};
</script>

<header class="page-header">
	<div class="header-content">
		<div class="logo"></div>
		<span class="heading_4">Pattern Factory</span>
	</div>
	<div class="header-controls">
		<button
			class="header-chat-button"
			on:click={onChatClick}
			title="Open chat"
			aria-label="Open pattern agent chat"
		>
			<i class="material-icons">chat</i>
		</button>
		<div class="header-search">
			<input
				type="text"
				placeholder="Search..."
				bind:value={$globalSearch}
				class="header-search-input"
				/>
		</div>
	</div>
</header>

<style>
	.page-header {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		height: 64px;
		background: #039be5;
		color: white;
		z-index: 10;
		display: flex;
		align-items: center;
		box-shadow: 0 2px 6px rgba(0,0,0,0.2);
	}

	.header-content {
		display: flex;
		align-items: center;
		gap: 1rem;
		padding-left: 1rem;
		width: 213px;
	}

	.logo {
		width: 40px;
		height: 40px;
		background: url('/img/logo_white.png') center/contain no-repeat;
		flex-shrink: 0;
	}

	.header-controls {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-left: auto;
		padding-right: 1.5rem;
	}

	.header-chat-button {
		background: none;
		border: none;
		cursor: pointer;
		padding: 0.5rem;
		border-radius: 4px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: white;
		transition: all 0.2s ease;
	}

	.header-chat-button:hover {
		background-color: rgba(255, 255, 255, 0.1);
	}

	.header-chat-button i {
		font-size: 24px;
	}

	.header-search {
		display: flex;
		align-items: center;
	}

	.header-search-input {
		padding: 0.5rem 0.75rem;
		border: 1px solid rgba(255, 255, 255, 0.3);
		border-radius: 4px;
		background-color: rgba(255, 255, 255, 0.9);
		width: 250px;
		font-family: 'Roboto', system-ui, -apple-system, sans-serif;
		font-size: 0.875rem;
		color: #495057;
	}

	.header-search-input::placeholder {
		color: #adb5bd;
	}

	.header-search-input:focus {
		outline: none;
		border-color: rgba(255, 255, 255, 0.6);
		background-color: white;
		box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.2);
	}
</style>
