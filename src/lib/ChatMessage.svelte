<script lang="ts">
	export let role: 'user' | 'agent' = 'user';
	export let content: string = '';
	export let timestamp: Date | null = null;
</script>

<div class="chat-message" class:user={role === 'user'} class:agent={role === 'agent'}>
	<div class="message-bubble">
		<div class="message-content">{content}</div>
		{#if timestamp}
			<div class="message-timestamp">
				{timestamp.toLocaleTimeString()}
			</div>
		{/if}
	</div>
</div>

<style>
	.chat-message {
		display: flex;
		margin: 0.75rem 0;
		animation: slideIn 0.3s ease-out;
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.chat-message.user {
		justify-content: flex-end;
	}

	.chat-message.agent {
		justify-content: flex-start;
	}

	.message-bubble {
		max-width: 70%;
		padding: 0.75rem 1rem;
		border-radius: 12px;
		word-wrap: break-word;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
	}

	.chat-message.user .message-bubble {
		background-color: #039be5;
		color: white;
		border-bottom-right-radius: 4px;
	}

	.chat-message.agent .message-bubble {
		background-color: #f5f5f5;
		color: rgba(0, 0, 0, 0.87);
		border-bottom-left-radius: 4px;
	}

	.message-content {
		font-size: 0.9375rem;
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.message-timestamp {
		font-size: 0.75rem;
		margin-top: 0.25rem;
		opacity: 0.7;
	}

	.chat-message.user .message-timestamp {
		text-align: right;
	}

	.chat-message.agent .message-timestamp {
		text-align: left;
	}
</style>
