<script lang="ts">
	let inputValue = '';
	let textareaElement: HTMLTextAreaElement;

	export let isLoading = false;
	export let onSend: (message: string) => void = () => {};

	function handleSendMessage() {
		if (inputValue.trim()) {
			onSend(inputValue.trim());
			inputValue = '';
			if (textareaElement) {
				textareaElement.style.height = 'auto';
			}
		}
	}

	function handleKeyDown(e: KeyboardEvent) {
		// Allow Cmd/Ctrl + Enter to send, or Enter without shift
		if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
			e.preventDefault();
			handleSendMessage();
		} else if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSendMessage();
		}
	}

	function handleTextareaInput() {
		if (textareaElement) {
			textareaElement.style.height = 'auto';
			textareaElement.style.height = Math.min(textareaElement.scrollHeight, 200) + 'px';
		}
	}
</script>

<div class="chat-input-container">
	<div class="input-wrapper">
		<textarea
			bind:this={textareaElement}
			bind:value={inputValue}
			placeholder="Ask me anything about patterns..."
			class="chat-textarea"
			on:keydown={handleKeyDown}
			on:input={handleTextareaInput}
			disabled={isLoading}
			rows="1"
		></textarea>
		<button
			class="send-button"
			on:click={handleSendMessage}
			disabled={isLoading || !inputValue.trim()}
			title="Send message (or press Enter)"
			aria-label="Send message"
		>
			{#if isLoading}
				<span class="spinner"></span>
			{:else}
				<i class="material-icons">arrow_upward</i>
			{/if}
		</button>
	</div>
</div>

<style>
	.chat-input-container {
		padding: 1rem;
		background-color: #fff;
		border-top: 1px solid #e0e0e0;
	}

	.input-wrapper {
		display: flex;
		gap: 0.75rem;
		align-items: flex-end;
		max-width: 100%;
	}

	.chat-textarea {
		flex: 1;
		padding: 0.75rem 1rem;
		border: 1px solid rgba(0, 0, 0, 0.12);
		border-radius: 24px;
		font-family: 'Roboto', Helvetica, Arial, sans-serif;
		font-size: 0.9375rem;
		line-height: 1.5;
		resize: none;
		max-height: 200px;
		min-height: 44px;
		transition: border-color 0.2s ease, box-shadow 0.2s ease;
		-webkit-appearance: none;
		-moz-appearance: none;
		appearance: none;
		overflow-y: auto;
	}

	.chat-textarea:focus {
		outline: none;
		border-color: #039be5;
		box-shadow: 0 0 0 2px rgba(3, 155, 229, 0.1);
	}

	.chat-textarea:hover:not(:disabled) {
		border-color: rgba(0, 0, 0, 0.2);
	}

	.chat-textarea:disabled {
		background-color: #fafafa;
		color: rgba(0, 0, 0, 0.38);
		cursor: not-allowed;
	}

	.send-button {
		width: 44px;
		height: 44px;
		border: none;
		border-radius: 50%;
		background-color: #039be5;
		color: white;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s ease;
		flex-shrink: 0;
		font-size: 0;
	}

	.send-button:hover:not(:disabled) {
		background-color: #0288d1;
		box-shadow: 0 2px 8px rgba(3, 155, 229, 0.3);
	}

	.send-button:active:not(:disabled) {
		background-color: #0277bd;
		transform: scale(0.95);
	}

	.send-button:disabled {
		background-color: #ccc;
		cursor: not-allowed;
		opacity: 0.6;
	}

	.send-button i {
		font-size: 20px;
		color: white;
	}

	.spinner {
		display: inline-block;
		width: 16px;
		height: 16px;
		border: 2px solid rgba(255, 255, 255, 0.3);
		border-top-color: white;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
