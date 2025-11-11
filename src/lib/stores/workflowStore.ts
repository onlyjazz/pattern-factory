import { writable } from "svelte/store";

function createPersistentStore<T>(key: string, initial: T) {
    // Safe fallback value
    const isBrowser = typeof window !== 'undefined';

    const storedValue = isBrowser
        ? JSON.parse(localStorage.getItem(key) || JSON.stringify(initial))
        : initial;
    const store = writable<T>(storedValue);

    if (isBrowser) {
        store.subscribe(value => {
            localStorage.setItem(key, JSON.stringify(value));
        });
    }

    return store;
}

export const workflowCode = createPersistentStore<string>('workflowCode', '');
export const workflowFilePath = createPersistentStore<string | null>('workflowFilePath', null);
export const isDirty = writable<boolean>(false); // Not persistent