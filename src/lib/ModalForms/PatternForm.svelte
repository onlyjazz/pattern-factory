<script lang="ts">
    let { newPattern, handleAddPattern } = $props();

    function submitForm(e) {
        e.preventDefault();
        handleAddPattern();
    }
</script>

<form onsubmit={submitForm} class="form">
    <div class="input">
        <input
            class="input__text"
            bind:value={newPattern.name}
            required
        />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label">Name</label>
    </div>

    <div class="input">
        <input
            class="input__text"
            bind:value={newPattern.description}
            required
        />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label">Description</label>
    </div>

    <div class="input">
        <input
            class="input__text"
            bind:value={newPattern.kind}
        />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label">Kind</label>
    </div>

    <button class="button button_blue button_blocked" type="submit">
        Save Pattern
    </button>
</form>

<style>
    .form {
        padding-top: 1rem;
    }
</style>