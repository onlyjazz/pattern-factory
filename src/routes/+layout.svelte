<script>
    import '../app.css';
    import Header from '$lib/Header.svelte';
    import Sidebar from '$lib/Sidebar.svelte';
    import ChatDrawer from '$lib/ChatDrawer.svelte';

    let { children } = $props();
    let chatDrawerOpen = $state(false);

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
