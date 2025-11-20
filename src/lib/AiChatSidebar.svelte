<!-- AiChatSidebar.svelte -->
<script lang="ts">
  import AiChat from './AiChat.svelte';
  import { onMount, onDestroy } from 'svelte';
  import { getDslCode } from '$lib/globalDsl';

  let isOpen = true;
  let loadedCode = ``;
  let activeTab = 'chat';

  function toggleSidebar() {
    loadedCode = getDslCode();
  }

  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape' && isOpen) {
      isOpen = false;
    }
  }

  onMount(() => {
    loadedCode = getDslCode();
    console.log('Code from page:', loadedCode);
  });
</script>

{#if !isOpen}
  <button class="toggle-btn" onclick={toggleSidebar}>
    <span class="material-icons">chat</span>
  </button>
{/if}

<!--Overlay div-->
<div class="overlay" class:is-open={isOpen} onclick={toggleSidebar}></div>

<div class="sidebar" class:is-open={isOpen}>
  <div class="sidebar-content">
    <button class="toggle-btn toggle-btn_close" onclick={toggleSidebar}>
      <span class="material-icons">close</span>
    </button>
    <div class="tabs">
      <button class="tab-button code-button" onclick={() => activeTab = 'code'} class:active={activeTab === 'code'}>
        🛠️ Code
      </button>
      <button class="tab-button chat-button" onclick={() => activeTab = 'chat'} class:active={activeTab === 'chat'}>
        💬 AI Chat
      </button>
    </div>

    <div class="chat-wrapper">
        <AiChat dslCode={loadedCode} />
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0);
    z-index: 998;
    backdrop-filter: blur(0);
    opacity: 0;
    transition: opacity 0.3s ease, backdrop-filter 0.3s ease;
    pointer-events: none;
  }
  .overlay.is-open {
    opacity: 1;
    background-color: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(1px);
    pointer-events: auto;
  }
  .sidebar {
    position: fixed;
    top: 0;
    right: 0;
    height: 100vh;
    width: 45%;
    background-color: #ffffff; /* white background */
    transition: transform 0.3s ease;
    transform: translateX(100%);
    z-index: 999;
    box-shadow: -2px 0 5px rgba(0, 0, 0, 0.3);
    display: flex;
    flex-direction: column;
  }
  .sidebar-content {
    background-color: #ffffff;
  }

  .sidebar.is-open {
    transform: translateX(0);
  }

  .chat-wrapper {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .toggle-btn {
    position: fixed;
    bottom: 1rem;
    right: 1rem;
    z-index: 1000;
    background-color: #03A9F4;
    border: none;
    border-radius: 50%;
    color: white;
    font-size: 1.5rem;
    padding: 0.5rem;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
  }

  .toggle-btn_close{
      top: 0.5rem;
      right: 1.2rem;
      bottom: auto;
      height: 2rem;
      width: 2rem;
      box-shadow: -2px 2px 5px rgba(0, 0, 0, 0.3);
  }

  .tabs {
    display: flex;
    justify-content: center;
  }

  .tab-button {
    width: 50%;
    border: none;
    background-color: #f0f0f0;
  }

  .tab-button.active {
    background-color: #ffffff;
  }
</style>
