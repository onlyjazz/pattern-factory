import { writable, get } from 'svelte/store';

type Rows = Record<string, any>[];

const _registry = writable(new Map<string, Rows>());

export const tableRegistry = {
  subscribe: _registry.subscribe,
  save(tableId: string, rows: Rows) {
    _registry.update((m) => {
      const copy = new Map(m);
      copy.set(tableId, rows);
      return copy;
    });
  },
  get(tableId: string): Rows | undefined {
    return get(_registry).get(tableId);
  },
  has(tableId: string): boolean {
    return get(_registry).has(tableId);
  },
  remove(tableId: string) {
    _registry.update((m) => {
      const copy = new Map(m);
      copy.delete(tableId);
      return copy;
    });
  }
};
