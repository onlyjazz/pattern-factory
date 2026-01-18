<script>
    import '../app.css';
    import Header from '$lib/Header.svelte';
    import Sidebar from '$lib/Sidebar.svelte';
    import ChatDrawer from '$lib/ChatDrawer.svelte';
    import { modeStore } from '$lib/modeStore';
    import { onMount } from 'svelte';

    let { children } = $props();
    let chatDrawerOpen = $state(false);

    onMount(() => {
        // Mode store is initialized on mount via its own initialization logic
        // This ensures localStorage is accessible on the client side
    });

    function handleChatClick() {
        chatDrawerOpen = true;
    }

    function handleChatClose() {
        chatDrawerOpen = false;
    }
</script>

<div class="page">
    <Header onChatClick={handleChatClick} />
    <Sidebar />
    <ChatDrawer isOpen={chatDrawerOpen} onClose={handleChatClose} />
    <main class="page-content">
        {@render children()}
    </main>
</div>
