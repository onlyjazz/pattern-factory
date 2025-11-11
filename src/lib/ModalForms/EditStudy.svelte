<script lang="ts">
    import { selectedStudy } from '$lib/selectedStudy';
    import { studies } from '$lib/stores/studies';
    import { get } from 'svelte/store';
    import type { Study } from '$lib/stores/studies';

    // Get the selected study
    const selected = get(selectedStudy);

    export let showEditModal: boolean;
    
    // Create a copy of the selected study for editing
    let editedStudy: Study = selected ? { ...selected } : {
        name: '',
        customer: '',
        rules: 0,
        recruitment: '',
        data: '',
        status: 'Active',
        selected: false,
        code: ''
    };

    // Handle form submission
    function handleEditStudy() {
        if (!selected) return;
        
        // Update the study in the store
        studies.update(list => {
            const index = list.findIndex(s => s.name === selected.name);
            if (index !== -1) {
                list[index] = { ...editedStudy };
            }
            return list;
        });

        // Close the modal
        showEditModal = false;
    }

    // Close the modal if no study is selected
    $: if (!selected && showEditModal) {
        showEditModal = false;
    }
</script>

<form on:submit|preventDefault={handleEditStudy} class="grid-row">
    <div class="grid-col grid-col_24 mb-3 mt-3">
        <div class="input">
            <input 
                id="name" 
                type="text" 
                class="input__text"
                class:input__text_changed={editedStudy.name.length > 0}
                bind:value={editedStudy.name} 
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
                class:input__text_changed={editedStudy.customer.length > 0}
                bind:value={editedStudy.customer} 
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
                class:input__text_changed={editedStudy.recruitment.length > 0}
                bind:value={editedStudy.recruitment} 
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
                class:input__text_changed={editedStudy.data.length > 0}
                bind:value={editedStudy.data} 
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
                class:input__text_changed={editedStudy.status.length > 0}
                bind:value={editedStudy.status} 
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
            {selected ? 'Update Study' : 'Add Study'}
        </button>
    </div>
</form>

<style>
    @import "../../main.css"
</style>