<script lang="ts">
    import type { Card } from '$lib/api';
    import CodeMirror from "svelte-codemirror-editor";
    import { basicSetup } from "@codemirror/basic-setup";
    import { python } from "@codemirror/lang-python";
    
    export let card: Card;
    export let onSave: (updatedCard: Card) => void;
    export let onClose: () => void;

    let editedCard: Card = {...card};
    let extensions = [basicSetup, python()];

    function handleSubmit() {
        const now = new Date().toISOString();
        editedCard.date_amended = now;
        onSave(editedCard);
        onClose();
    }
</script>

<form on:submit|preventDefault={handleSubmit} class="grid-row">
    <div class="grid-col grid-col_24 mb-3 mt-3">
        <div class="input">
            <input
                id="sponsor"
                type="text"
                class="input__text"
                class:input__text_changed={editedCard.sponsor.length > 0}
                bind:value={editedCard.sponsor}
                required
            />
            <label class="input__label">Sponsor</label>
        </div>
    </div>

    <div class="grid-col grid-col_24 mb-3">
        <div class="input">
            <input
                id="protocol_id"
                type="text"
                class="input__text"
                class:input__text_changed={editedCard.protocol_id.length > 0}
                bind:value={editedCard.protocol_id}
                required
            />
            <label class="input__label">Protocol ID</label>
        </div>
    </div>

    <div class="grid-col grid-col_24 mb-3">
        <label class="label" style="display: block; margin-bottom: 0.5rem;">System Prompt</label>
        <CodeMirror 
            bind:value={editedCard.prompt}
            {extensions}
            styles={{
                "&": {
                    width: "100%",
                    maxWidth: "100%",
                    height: "600px",
                    border: "1px solid #ccc",
                    borderRadius: "4px"
                }
            }}
        />
    </div>

    <div class="grid-col grid-col_24 mb-3">
        <div class="input">
            <input
                id="agent"
                type="text"
                class="input__text"
                class:input__text_changed={editedCard.agent.length > 0}
                bind:value={editedCard.agent}
                required
            />
            <label class="input__label">Agent</label>
        </div>
    </div>

    <div class="grid-col grid-col_24">
        <div class="button-group">
            <button type="submit" class="button button_green">
                Save Changes
            </button>
        </div>
    </div>
</form>

<style>
    @import "../../main.css";
</style>
  