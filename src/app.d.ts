// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}

	// Google Charts / Maps globals loaded via <script src> at runtime.
	const google: any;
	interface Window {
		google: any;
	}
}

export {};
