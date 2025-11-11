import { writable } from 'svelte/store';
import { fetchProtocols } from '$lib/api';

export interface Study {
    name: string;
    customer: string;
    rules: number;
    recruitment: string;
    data: string;
    status: string;
    selected: boolean;
    code?: string;
}

function createStudiesStore() {
    const { subscribe, set, update } = writable<Study[]>([]);

    return {
        subscribe,
        set,
        update,
        refresh: async () => {
            const protocols = await fetchProtocols();

            const studies = protocols.map(p => ({
                name: p.protocol_id,
                customer: p.sponsor,
                rules: 0, // Placeholder
                recruitment: 'Ongoing', // You can adjust or fetch this
                data: p.data,
                status: p.status || 'Active',
                selected: false,
                code: ''
            }));

            set(studies);
        }
    };
}

export const studies = createStudiesStore();
