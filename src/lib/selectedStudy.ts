import { writable } from 'svelte/store';
import type { Study } from '$lib/stores/studies';

// Check if we're in the browser before using localStorage
const isBrowser = typeof window !== 'undefined';

const saved = isBrowser ? localStorage.getItem('selectedStudy') : null;
const initial: Study | null = saved ? JSON.parse(saved) : null;

export const selectedStudy = writable<Study | null>(initial);

if (isBrowser) {
  selectedStudy.subscribe((value) => {
    if (value) {
      localStorage.setItem('selectedStudy', JSON.stringify(value));
    } else {
      localStorage.removeItem('selectedStudy');
    }
  });
}
