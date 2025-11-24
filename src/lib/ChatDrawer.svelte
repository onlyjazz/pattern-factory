<script lang="ts">
	import ChatInterface from './ChatInterface.svelte';

	export let isOpen = false;
	export let onClose = () => {};

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			onClose();
		}
	}

	function handleEscapeKey(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		}
	}
</script>

<svelte:window on:keydown={handleEscapeKey} />

<div class="chat-drawer-overlay" class:open={isOpen} on:click={handleBackdropClick} role="presentation">
	<div class="chat-drawer">
		<ChatInterface {onClose} />
	</div>
</div>

<style>
	.chat-drawer-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: rgba(0, 0, 0, 0.5);
		display: flex;
		justify-content: flex-end;
		z-index: 1000;
		pointer-events: none;
		opacity: 0;
		transition: opacity 0.3s ease;
	}

	.chat-drawer-overlay.open {
		pointer-events: auto;
		opacity: 1;
	}

	.chat-drawer {
		width: 100%;
		max-width: 500px;
		height: 100%;
		background-color: white;
		box-shadow: -2px 0 8px rgba(0, 0, 0, 0.15);
		display: flex;
		flex-direction: column;
		transform: translateX(100%);
		transition: transform 0.3s ease;
		overflow: hidden;
	}

	.chat-drawer-overlay.open .chat-drawer {
		transform: translateX(0);
	}

	/* Responsive design for smaller screens */
	@media screen and (max-width: 768px) {
		.chat-drawer {
			max-width: 100%;
		}
	}
</style>
