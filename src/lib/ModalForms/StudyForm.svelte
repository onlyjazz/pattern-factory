<script lang="ts">
    import type { Study } from '$lib/stores/studies';

    export let handleAddStudy: () => void;
    export let newStudy: Study;
</script>

<form on:submit|preventDefault={handleAddStudy} class="grid-row">
    <div class="grid-col grid-col_24 mb-3 mt-3">
        <div class="input">
            <input 
                id="name" 
                type="text" 
                class="input__text"
                class:input__text_changed={newStudy.name.length > 0}
                bind:value={newStudy.name} 
                required
            >
            <label class="input__label">Name</label>
        </div>
    </div>
    
    <div class="grid-col grid-col_24 mb-3">
        <div class="input">
            <input 
                id="customer" 
                type="text" 
                class="input__text"
                class:input__text_changed={newStudy.customer.length > 0}
                bind:value={newStudy.customer} 
                required
            >
            <label class="input__label">Customer</label>
        </div>
    </div>
    
    <div class="grid-col grid-col_24 mb-3">
        <div class="input">
            <input 
                id="recruitment" 
                type="text" 
                class="input__text"
                class:input__text_changed={newStudy.recruitment.length > 0}
                bind:value={newStudy.recruitment} 
                required
            >
            <label class="input__label">Recruitment</label>
        </div>
    </div>
    
    <div class="grid-col grid-col_24 mb-3">
        <div class="input">
            <input 
                id="data" 
                type="text" 
                class="input__text" 
                class:input__text_changed={newStudy.data.length > 0}
                bind:value={newStudy.data} 
                required
            >
            <label class="input__label">Date</label>
        </div>
    </div>
    
    <div class="grid-col grid-col_24 mb-4">
        <div class="input input_select">
            <select 
                id="status" 
                class="input__text" 
                class:input__text_changed={newStudy.status.length > 0}
                bind:value={newStudy.status} 
                required
            >
                <option value="Draft">Draft</option>
                <option value="Active">Active</option>
                <option value="Completed">Completed</option>
            </select>
            <label class="input__label">Status</label>
        </div>
    </div>
    
    <div class="grid-col grid-col_24">
        <button type="submit" class="button button_green button_block">
            Add Study
        </button>
    </div>
</form>

<style>
    @import "../../main.css"
</style>