<script>
    import '../app.css';
    import Header from '$lib/Header.svelte';
    import Sidebar from '$lib/Sidebar.svelte';

    let { children } = $props();
</script>

<div class="page">
    <Header />
    <Sidebar />
    <main class="page-content">
        {@render children()}
    </main>
</div>
