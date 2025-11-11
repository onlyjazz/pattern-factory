import { writable } from 'svelte/store';

export const darkMode = writable(false);

if (typeof window !== 'undefined') {
	const stored = localStorage.getItem('darkMode') === 'true';
	darkMode.set(stored);

	darkMode.subscribe((value) => {
		localStorage.setItem('darkMode', value.toString());
		document.body.classList.toggle('dark', value);
	});
}
