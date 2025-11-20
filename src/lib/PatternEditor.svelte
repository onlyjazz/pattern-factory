<script lang="ts">
    let { pattern, onSave } = $props();

    // Local copy so edits don’t mutate original until saved
    // svelte-ignore non_reactive_update
    let local = {
        name: pattern?.name ?? "",
        description: pattern?.description ?? "",
        kind: pattern?.kind ?? ""
    };

    // When editing, update local values when pattern changes
    $effect(() => {
        if (pattern) {
            local = {
                name: pattern.name ?? "",
                description: pattern.description ?? "",
                kind: pattern.kind ?? ""
            };
        }
    });

    function submitForm(e: Event) {
        e.preventDefault();
        console.log("SUBMIT →", local);
        console.log("PLAIN →", { ...local });
        onSave({ ...local });    // emit a plain object
    }
</script>

<form class="form" onsubmit={submitForm}>
    <div class="input">
        <input
            id="pattern-name"
            class="input__text"
            bind:value={local.name}
            required
        />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label" for="pattern-name">Name</label>
    </div>

    <div class="input">
        <input
            id="pattern-description"
            class="input__text"
            bind:value={local.description}
            required
        />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label" for="pattern-description">Description</label>
    </div>

    <div class="input">
        <input
            id="pattern-kind"
            class="input__text"
            bind:value={local.kind}
        />
        <!-- svelte-ignore a11y_label_has_associated_control -->
        <label class="input__label" for="pattern-kind">Kind</label>
    </div>

    <button class="button button_green button_blocked" type="submit">
        Save
    </button>
</form>

<style>
.form {
    padding-top: 1rem;
}
</style>
