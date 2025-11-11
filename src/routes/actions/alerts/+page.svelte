<script lang="ts">
    import { selectedStudy } from '$lib/selectedStudy';
    import { onMount } from 'svelte';
    import { getAlerts } from '$lib/api';
    import { formatDate } from '$lib';
    
    interface Alert {
        subjid: string;
        protocol_id: string;
        crf: string;
        variable: string;
        variable_value: number;
        rule_id: string;
        status: number;
        date_created: string; // ISO timestamp
    }

    let alerts: Alert[] = [];

    onMount(async () => {
        try {
            alerts = await getAlerts();
            console.log('Fetched alerts:', alerts);
        } catch (error) {
            console.error('Error fetching alerts:', error);
        }
    });
</script>

<div class="page-title">
    <div class="heading heading_1">Data review</div>
</div>

<div class="grid-row">
    <div class="grid-col grid-col_24">
        <div class="card">
            <div class="table">
                <table>
                    <thead>
                        <tr>
                            <th class="tal">Subject ID</th>
                            <th class="tal">Protocol ID</th>
                            <th class="tal">CRF</th>
                            <th class="tar">Variable</th>
                            <th class="tar">Value</th>
                            <th class="tar">Rule ID</th>
                            <th class="tar">Date</th>
                            <th class="tar">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {#each alerts as alert}
                            <tr>
                                <td class="tal">{alert.subjid}</td>
                                <td class="tal">{alert.protocol_id}</td>
                                <td class="tar">{alert.crf}</td>
                                <td class="tar">{alert.variable}</td>
                                <td class="tar">{alert.variable_value}</td>
                                <td class="tar">{alert.rule_id}</td>
                                <td class="tar">{formatDate(alert.date_created)}</td>
                                <td class="tar c_{alert.status === 0 ? 'green' : alert.status === 1 ? 'blue' : 'red'}">
                                    {alert.status === 0 ? 'Active' : alert.status === 1 ? 'Inactive' : 'Error'}
                                </td>
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