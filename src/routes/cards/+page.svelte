<script lang="ts">
    import { onMount } from 'svelte';
    import { getCards, addCard, deleteCard, updateCard } from '$lib/api';
    import type { Card } from '$lib/api';
    import { formatDate } from '$lib';
    import Modal from '$lib/Modal.svelte';
    import AddCard from '$lib/ModalForms/AddCard.svelte';
    import EditCard from '$lib/ModalForms/EditCard.svelte';

    let cards: Card[] = [];
    let loading = true;
    let error: string | null = null;
    let showAddModal = false;
    let showEditModal = false;
    let cardToEdit: Card | null = null;

    let newCard: Card = {
        sponsor: '',
        protocol_id: '',
        prompt: '',
        agent: '',
        date_created: '',
        date_amended: ''
    };

    onMount(async () => {
        try {
            cards = await getCards();
        } catch (err) {
            console.error('Error fetching cards:', err);
            error = 'Failed to load cards.';
        } finally {
            loading = false;
        }
    });

    async function handleAddCard() {
        try {
            await addCard(newCard);
            // Refresh the cards from the database to get the properly saved data
            cards = await getCards();
            showAddModal = false;

            newCard = {
                sponsor: '',
                protocol_id: '',
                prompt: '',
                agent: '',
                date_created: '',
                date_amended: ''
            };
        } catch (err) {
            console.error('Failed to add card:', err);
        }
    }

    async function handleUpdateCard(updatedCard: Card) {
        console.log('handleUpdateCard called with:', updatedCard);
        try {
            // Update the card in the database
            await updateCard(updatedCard);
            console.log('Card updated in database');
            
            // Refresh the cards from the database to get the properly saved data
            cards = await getCards();
            
            console.log('Cards refreshed, closing modal');
        } catch (err) {
            console.error('Failed to update card:', err);
        } finally {
            console.log('Finally block executing');
            showEditModal = false;
            cardToEdit = null;
        }
    }

    function handleEditClick(card: Card) {
        cardToEdit = { ...card };
        showEditModal = true;
    }
</script>

<div class="page-title">
    <heading class="heading_1">Cards</heading>
    <button class="button button_green" on:click={() => (showAddModal = true)}>
        Add Card
    </button>
</div>

<div class="grid-row">
    <div class="grid-col grid-col_24">
        <div class="card">
            {#if loading}
                <p>Loading cards...</p>
            {:else if error}
                <p>Error: {error}</p>
            {:else if cards.length === 0}
                <p>No cards found.</p>
            {:else}
                <div class="table">
                    <table>
                        <thead>
                            <tr>
                                <th>Sponsor</th>
                                <th>Protocol ID</th>
                                <th>Card</th>
                                <th>Agent</th>
                                <th>Date Created</th>
                                <th>Date Amended</th>
                            </tr>
                        </thead>
                        <tbody>
                            {#each cards as card}
                                <tr>
                                    <td><a href="#" on:click|preventDefault={() => handleEditClick(card)}>{card.sponsor}</a></td>
                                    <td>{card.protocol_id}</td>
                                    <td style="white-space: pre-wrap; max-width: 300px;">{card.prompt}</td>
                                    <td>{card.agent}</td>
                                    <td>{formatDate(card.date_created)}</td>
                                    <td>{formatDate(card.date_amended)}</td>
                                    <td class="actions">
                                        <button class="edit-button" on:click={() => handleEditClick(card)}>
                                            Edit
                                        </button>
                                        <button class="x-button" on:click={async () => {
                                            try {
                                                await deleteCard(card.sponsor, card.protocol_id, card.prompt);
                                                // Refresh the cards after successful deletion
                                                cards = await getCards();
                                            } catch (error) {
                                                console.error('Error deleting card:', error);
                                                error = 'Failed to delete card.';
                                            }
                                        }}>
                                            X
                                        </button>
                                    </td>
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
            {/if}
        </div>
    </div>
</div>

<Modal bind:showModal={showAddModal}>
    {#snippet header()}
        <h2>Add Card</h2>
    {/snippet}
    {#snippet children()}
        <AddCard {handleAddCard} newCard={newCard} />
    {/snippet}
</Modal>

<Modal bind:showModal={showEditModal}>
    {#snippet header()}
        <h2>Edit Card</h2>
    {/snippet}
    {#snippet children()}
        {#if cardToEdit}
            <EditCard 
                card={cardToEdit} 
                onSave={async (updatedCard) => {
                    try {
                        await handleUpdateCard(updatedCard);
                    } catch (error) {
                        console.error('Error updating card:', error);
                    }
                }} 
                onClose={() => {
                    showEditModal = false;
                    cardToEdit = null;
                }}
            />
        {/if}
    {/snippet}
</Modal>

<style>
    .actions {
        display: flex;
        gap: 0.5rem;
    }

    .edit-button {
        background-color: #4CAF50;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        cursor: pointer;
    }

    .x-button {
        background-color: #f44336;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 4px;
        cursor: pointer;
    }
</style>
