import { writable } from 'svelte/store';
import type { Pattern } from '$lib/stores/patterns';

// Check browser environment before using localStorage
const isBrowser = typeof window !== 'undefined';

// Restore previous selection from localStorage
const saved = isBrowser ? localStorage.getItem('selectedPattern') : null;
const initial: Pattern | null = saved ? JSON.parse(saved) : null;

// Export the writable store
export const selectedPattern = writable<Pattern | null>(initial);

// Persist changes to localStorage
if (isBrowser) {
  selectedPattern.subscribe((value) => {
    if (value) {
      localStorage.setItem('selectedPattern', JSON.stringify(value));
    } else {
      localStorage.removeItem('selectedPattern');
    }
  });
}
