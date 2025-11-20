<script lang="ts">
    let { patternToEdit, onSave } = $props();

    let local = $state({
        name: patternToEdit?.name ?? "",
        description: patternToEdit?.description ?? "",
        kind: patternToEdit?.kind ?? ""
    });

    // 🔥 Always update form fields when parent updates patternToEdit
    $effect(() => {
        if (patternToEdit) {
            local = {
                name: patternToEdit.name ?? "",
                description: patternToEdit.description ?? "",
                kind: patternToEdit.kind ?? ""
            };
        }
    });

    function submitForm(e) {
        e.preventDefault();
        onSave(local);
    }
</script>

<form onsubmit={submitForm} class="form">
    <div class="input">
        <input class="input__text" bind:value={local.name} required />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label">Name</label>
    </div>

    <div class="input">
        <input class="input__text" bind:value={local.description} required />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label">Description</label>
    </div>

    <div class="input">
        <input class="input__text" bind:value={local.kind} />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label">Kind</label>
    </div>

    <button class="button button_green button_blocked" type="submit">
        Update Pattern
    </button>
</form>

<style>
    .form {
        padding-top: 1rem;
    }
</style>
