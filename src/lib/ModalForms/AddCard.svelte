<script lang="ts">
    import type { Card } from '$lib/api';
    import CodeMirror from "svelte-codemirror-editor";
    import { basicSetup } from "@codemirror/basic-setup";
    import { python } from "@codemirror/lang-python";
    
    export let handleAddCard: () => void;
    export let newCard: Card;
    
    let extensions = [basicSetup, python()];

    function handleSubmit() {
        const now = new Date().toISOString();
        newCard.date_created = now;
        newCard.date_amended = now;
        handleAddCard();
    }
</script>

<form on:submit|preventDefault={handleSubmit} class="grid-row">
    <div class="grid-col grid-col_24 mb-3 mt-3">
        <div class="input">
            <input
                id="sponsor"
                type="text"
                class="input__text"
                class:input__text_changed={newCard.sponsor.length > 0}
                bind:value={newCard.sponsor}
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
                class:input__text_changed={newCard.protocol_id.length > 0}
                bind:value={newCard.protocol_id}
                required
            />
            <label class="input__label">Protocol ID</label>
        </div>
    </div>

    <div class="grid-col grid-col_24 mb-3">
        <label class="label" style="display: block; margin-bottom: 0.5rem;">System Prompt</label>
        <CodeMirror 
            bind:value={newCard.prompt}
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
                class:input__text_changed={newCard.agent.length > 0}
                bind:value={newCard.agent}
                required
            />
            <label class="input__label">Agent</label>
        </div>
    </div>

    <div class="grid-col grid-col_24">
        <button type="submit" class="button button_green button_block">
            Add Card
        </button>
    </div>
</form>

<style>
    @import "../../main.css";
</style>
  