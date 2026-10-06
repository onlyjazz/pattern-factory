import { writable } from 'svelte/store';

const STORAGE_KEY = 'pf:globalSearch';

function createGlobalSearchStore() {
	// Initialize from sessionStorage. List pages navigate into detail pages with
	// full page loads (window.location.href), so a plain in-memory store would be
	// reset on every click. Persisting per tab keeps the filter applied while the
	// user drills into related people, products, and orgs.
	let initial = '';
	if (typeof window !== 'undefined') {
		initial = sessionStorage.getItem(STORAGE_KEY) ?? '';
	}

	const { subscribe, set, update } = writable(initial);

	// Subscribe to changes and persist to sessionStorage
	if (typeof window !== 'undefined') {
		subscribe((value) => {
			if (value) {
				sessionStorage.setItem(STORAGE_KEY, value);
			} else {
				sessionStorage.removeItem(STORAGE_KEY);
			}
		});
	}

	return {
		subscribe,
		set,
		update,
		clear() {
			set('');
		}
	};
}

export const globalSearch = createGlobalSearchStore();
