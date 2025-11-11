<script lang="ts">
    import { onMount } from 'svelte';
    import { fetchRules } from '$lib/api';
    import { formatDate } from '$lib';
    import { selectedStudy } from '$lib/selectedStudy';

    let rules: {rule_id: string; protocol_id: string; sponsor: string; rule_code: string; date_created: string; date_amended: string }[] = [];

    onMount(async () => {
        rules = await fetchRules();
        console.log("Fetched rules:", rules, rules.length);
    });
</script>

<div class="page-title">
    <h1 class="heading heading_1">Rules</h1>
</div>

<div class="grid-row">
    <div class="grid-col grid-col_24">
        <div class="card">
            <div class="table">
                <table>
                    <thead>
                        <tr>
                            <th class="tal">Rule ID</th>
                            <th class="tal">Protocol ID</th>
                            <th class="tal">Sponsor</th>
                            <th class="tal">Rule Code</th>
                            <th class="tal">Date Created</th>
                            <th class="tal">Date Amended</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each rules as rule}
                            <tr>
                                <td class="tal">{rule.rule_id}</td>
                                <td class="tal">{rule.protocol_id}</td>
                                <td class="tal">{rule.sponsor}</td>
                                <td class="tal">{rule.rule_code}</td>
                                <td class="tal">{formatDate(rule.date_created)}</td>
                                <td class="tal">{formatDate(rule.date_amended)}</td>
                            </tr>
                        {/each}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<style>
</style>