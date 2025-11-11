<script>
    import { onMount } from 'svelte';
    
    let { showModal = $bindable(), header, children } = $props();
    let dialog = $state();
    let isOpen = $state(false);

    $effect(() => {
        if (showModal && !isOpen) {
            dialog.showModal();
            isOpen = true;
        } else if (!showModal && isOpen) {
            dialog.close();
            isOpen = false;
        }
    });

    function closeModal() {
        showModal = false;
        isOpen = false;
        if (dialog) {
            dialog.close();
        }
    }

    function handleKeyDown(e) {
        if (e.key === 'Escape') {
            closeModal();
        }
    }
</script>

<svelte:window on:keydown={handleKeyDown} />

<dialog 
    bind:this={dialog}
    on:close={closeModal}
    on:click|self={closeModal}
>
    <div class="modal-container">
        <button class="close-button" on:click={closeModal} aria-label="Close">
            <span class="material-icons">close</span>
        </button>
        <div class="modal-content">
            {@render header?.()}
            <hr />
            {@render children?.()}
        </div>
    </div>
</dialog>

<style>
    @import "../main.css";
    
    dialog {
        max-width: 60em; /* Increased width */
        max-height: 90vh; /* Limit height to viewport */
        width: 90%;
        padding: 0;
        border-radius: 8px;
        border: none;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        overflow: hidden;
    }
    
    dialog::backdrop {
        background: rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(2px);
    }
    
    .modal-container {
        position: relative;
        max-height: 90vh;
        display: flex;
        flex-direction: column;
    }
    
    .modal-content {
        padding: 2rem;
        overflow-y: auto;
        max-height: calc(90vh - 100px);
    }
    
    .close-button {
        position: absolute;
        top: 1rem;
        right: 1rem;
        width: 2.5rem;
        height: 2.5rem;
        border-radius: 50%;
        background: #f0f0f0;
        border: none;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        z-index: 10;
        transition: background-color 0.2s;
    }
    
    .close-button:hover {
        background: #e0e0e0;
    }
    
    .close-button .material-icons {
        font-size: 1.5rem;
        color: #555;
    }
    
    dialog[open] {
        animation: zoom 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    @keyframes zoom {
        from {
            transform: scale(0.5);
        }
        to {
            transform: scale(1);
        }
    }
    dialog[open]::backdrop {
        animation: fade 0.2s ease-out;
    }
    @keyframes fade {
        from {
            opacity: 0;
        }
        to {
            opacity: 1;
        }
    }
</style>