<script lang="ts">
    import { onMount } from 'svelte';
    let open = $state(false);
    let triggerRef = $state<HTMLElement | null>(null);
    let menuRef = $state<HTMLElement | null>(null);

    const { onEdit = () => {}, onDelete = () => {} } = $props();

    function toggle() {
        open = !open;
    }
    function close() {
        open = false;
    }

    function handleOutside(e: MouseEvent) {
        if (
            open &&
            menuRef &&
            triggerRef &&
            !menuRef.contains(e.target as Node) &&
            !triggerRef.contains(e.target as Node)
        ) {
            close();
        }
    }

    onMount(() => {
        window.addEventListener("click", handleOutside);
        return () => window.removeEventListener("click", handleOutside);
    });
</script>

<div class="action-menu">
    <button
        class="trigger"
        bind:this={triggerRef}
        onclick={toggle}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Actions"
    >
        <span class="material-icons">more_vert</span>
    </button>

    {#if open}
        <div class="menu" bind:this={menuRef} role="menu">
            <button
                class="item"
                onclick={() => { close(); onEdit(); }}
                role="menuitem"
            >
                <span class="material-icons">edit</span> Edit
            </button>

            <button
                class="item delete"
                onclick={() => { close(); onDelete(); }}
                role="menuitem"
            >
                <span class="material-icons">delete</span> Delete
            </button>
        </div>
    {/if}
</div>

<style>
.action-menu {
    position: relative;
    display: inline-block;
}
.trigger {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    font-size: 22px;
    color: #616161;
    display: flex;
    align-items: center;
}
.menu {
    position: absolute;
    right: 0;
    top: 28px;
    width: 130px;
    background: white;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    border-radius: 4px;
    padding: 6px 0;
    z-index: 1000;
}
.item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 14px;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 14px;
    color: #333;
}
.item:hover {
    background: #eee;
}
.item.delete {
    color: #d32f2f;
}
</style>
