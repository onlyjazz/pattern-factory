<script lang="ts">
    import AiChat from '$lib/AiChat.svelte';
    import CodeBox from '$lib/CodeBox.svelte';

    let activeTab: 'code' | 'chat' = 'code';
</script>

<style>
    @import url('https://fonts.googleapis.com/css?family=Roboto:300,400,500,700');
    .tabs {
        display: flex;
    }

    .tab-button {
        background-color: white;
        border: none;
        padding: 0.5rem 1rem;
        cursor: pointer;
        box-shadow: 0 -1px 3px rgba(0, 0, 0, 0.12),   /* top */
                    -1px 0 3px rgba(0, 0, 0, 0.12),   /* left */
                    1px 0 3px rgba(0, 0, 0, 0.12);    /* right */

    }

    .code-button {
        border-top-left-radius: 6px;
    }
    
    .chat-button {
        border-top-right-radius: 6px;
    }

    .tab-button.active {
        background-color: #2563eb;
        color: white;
    }

    .card {
        border-top-left-radius: 0;
    }
</style>

<div class="display: flex; justify-content: center; margin-top: 2rem;">
     <div class="width: 100%; max-width: 700px;">
        <div class="tabs">
            <button class="tab-button code-button" onclick={() => activeTab = 'code'} class:active={activeTab === 'code'}>
                🛠️ Code
            </button>
            <button class="tab-button chat-button" onclick={() => activeTab = 'chat'} class:active={activeTab === 'chat'}>
                💬 AI Chat
            </button>
        </div>
        <div class="card">
            <div class="tab-content">
                {#if activeTab === 'code'}
                    <CodeBox />
                {:else if activeTab === 'chat'}
                    <AiChat height="600px" />
                {/if}
            </div>
        </div>
     </div>
</div>
