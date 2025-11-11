import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit(),
	],
	resolve: {
		dedupe: [
			'@codemirror/state',
			'@codemirror/view',
			'@codemirror/autocomplete',
			'@codemirror/language',
			'@codemirror/lang-python',
			'@codemirror/text',
			'@codemirror/search',
			'@codemirror/commands',
			'@codemirror/stream-parser',
			'@codemirror/highlight'
		]
	}
});
