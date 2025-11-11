<script lang="ts">
	import { selectedStudy } from '$lib/selectedStudy';
	import { studies, type Study } from '$lib/stores/studies';
	import Modal from '$lib/Modal.svelte';
	import StudyForm from '$lib/ModalForms/StudyForm.svelte';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { addStudy } from '$lib/api';

	function handleSelect(event: Event) {
		const target = event.target as HTMLSelectElement;
		const value = target.value;
		if (value) goto(`/${value}`);
	}

	onMount(async () => {
		await studies.refresh();
	});

	let showModal = $state(false);

	let newStudy: Study = {
		name: '',
		customer: '',
		rules: 0,
		recruitment: '',
		data: '',
		status: '',
		selected: false,
		code: ''
	};

	async function handleAddStudy() {
		try {
			await addStudy(newStudy);
			await studies.refresh();
			showModal = false;
		} catch (error) {
			console.error('Failed to save study:', error);
			alert('Could not save the study.');
		}

		newStudy = {
			name: '',
			customer: '',
			rules: 0,
			recruitment: '',
			data: '',
			status: '',
			selected: false,
			code: ''
		};
	}

	function toggleSelection(index: number) {
		studies.update((list) => {
			list[index].selected = !list[index].selected;
			return list;
		});
	}

	function selectedStudies() {
		return $studies.filter((study) => study.selected);
	}

	let searchInput = '';
	let selectedStatus = 'All';
	let selectedCustomer = 'All';

	// ✅ Svelte 5 runes: computed values with $derived (no `$:`)
	let statuses = $derived([
		'All',
		...Array.from(new Set($studies.map((s) => s.status)).values())
	]);

	let customers = $derived([
		'All',
		...Array.from(new Set($studies.map((s) => s.customer)).values())
	]);

	let filteredStudies = $derived(
        $studies.filter((study) => {
            const matchesSearch = study.name.toLowerCase().includes(searchInput.toLowerCase());
            const matchesStatus = selectedStatus === 'All' || study.status?.trim().toLowerCase() === selectedStatus.trim().toLowerCase();
            const matchesCustomer = selectedCustomer === 'All' || study.status?.trim().toLowerCase() === selectedStatus.trim().toLowerCase();

            return matchesSearch && matchesStatus && matchesCustomer;
        })
    );
</script>

<div class="page-title">
	<button class="button button_green" onclick={() => (showModal = true)}>
		Add study
	</button>
	<h1 class="heading heading_1">Studies</h1>
</div>

<div class="grid-row">
	<div class="grid-col grid-col_6">
		<div class="filters card">
			<div class="heading heading_3">Filters</div>
			<div class="input">
				<input
					bind:value={searchInput}
					class:input__text_changed={searchInput.length > 0}
					class="input__text"
				/>
				<label class="input__label">Search by name</label>
			</div>
			<div class="input input_select">
				<select bind:value={selectedStatus} class="input__text input__text_changed">
					{#each statuses as status}
						<option>{status}</option>
					{/each}
				</select>
				<label class="input__label">Study status</label>
			</div>
			<div class="input input_select">
				<select bind:value={selectedCustomer} class="input__text input__text_changed">
					{#each customers as c}
						<option>{c}</option>
					{/each}
				</select>
				<label class="input__label">Customers</label>
			</div>
			<button type="submit" class="button button_blocked button_flat">Apply</button>
		</div>
	</div>

	<div class="grid-col grid-col_18">
		<div class="studies card">
			<div class="grid-row">
				<div class="grid-col grid-col_12">
					<div class="heading heading_3">Study portfolio</div>
				</div>
				<div class="grid-col grid-col_12 tar">
					<div class="button button_s button_flat">
						Actions
						<span class="material-icons" style="font-size: 16px; margin-left: 4px; vertical-align: middle;">
							arrow_drop_down
						</span>
						<select class="input__text input__text_changed" onchange={handleSelect}>
							<option value="" hidden>Select action</option>
							<option value="actions/ddt">Data Dictionary</option>
							<option value="actions/rules">Rules</option>
							<option value="actions/alerts">Data review</option>
							<option value="actions/protocol">Protocol</option>
							<option value="actions/workflow">Workflow</option>
						</select>
					</div>
				</div>
			</div>

			<div class="table">
				<table>
					<thead>
						<tr>
							<th class="tal">
								<label class="checkbox"><span class="material-icons">check</span></label>
							</th>
							<th class="tal"><a href="#" class="table__sort">Protocol ID</a></th>
							<th class="tal"><a href="#" class="table__sort">Customer</a></th>
							<th class="tar"><a href="#" class="table__sort">Rules</a></th>
							<th class="tar"><a href="#" class="table__sort">Recruitment</a></th>
							<th class="tar"><a href="#" class="table__sort">Date</a></th>
							<th class="tar"><a href="#" class="table__sort table__sort_down">Status</a></th>
						</tr>
					</thead>
					<tbody>
						{#each filteredStudies as study, i (i)}
							<tr style="cursor: pointer;" onclick={() => selectedStudy.set(study)}>
								<td class="tal">
									<label>
										<input
											type="radio"
											name="study"
											checked={$selectedStudy?.name === study.name}
											onchange={() => selectedStudy.set(study)}
										/>
									</label>
								</td>
								<td class="tal">{study.name}</td>
								<td class="tal">{study.customer}</td>
								<td class="tar">{study.rules}</td>
								<td class="tar">{study.recruitment}</td>
								<td class="tar">{study.data}</td>
								<td
									class={`tar c_${
										study.status.toLowerCase() === 'active'
											? 'green'
											: study.status.toLowerCase() === 'complete'
											? 'blue'
											: 'red'
									}`}
								>
									{study.status}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	</div>
</div>

<Modal bind:showModal={showModal}>
	{#snippet header()}
		<h2>Add study</h2>
	{/snippet}
	{#snippet children()}
		<StudyForm {handleAddStudy} {newStudy} />
	{/snippet}
</Modal>

<style>
</style>
