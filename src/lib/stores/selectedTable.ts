import { writable } from 'svelte/store';

export interface ResultTable {
  rule_id: string;
  table_name: string;
  row_count: number;
  created_at: string;
}

export const selectedTable = writable<ResultTable | null>(null);
