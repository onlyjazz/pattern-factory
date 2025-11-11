<script lang="ts">
    import Header from "../lib/Header.svelte";
    import Sidebar from "../lib/Sidebar.svelte";
    let { children } = $props();
</script>

<div class="page">
    <Header />
    <Sidebar />
    <main class="page-content">
        {@render children()}
    </main>
</div>

<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    @import url('https://fonts.googleapis.com/icon?family=Material+Icons');
    @import "../main.css";

    :global(html) {
        font-family: 'Roboto', system-ui, -apple-system, sans-serif;
    }
</style>