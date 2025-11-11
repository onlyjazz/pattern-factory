import { writable } from 'svelte/store';

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

export const dslCode = createPersistentStore<string>('dslCode', '');
export const dslFilePath = createPersistentStore<string | null>('dslFilePath', null);
export const isDirty = writable<boolean>(false); // Not persisted unless you want to
