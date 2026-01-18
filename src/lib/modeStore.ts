import { writable } from 'svelte/store';

export type AppMode = 'explore' | 'model';

interface ModeState {
	mode: AppMode;
	activeModel: number | null;
	activeModelName: string | null;
}

const STORAGE_KEY_MODE = 'pf:mode';
const STORAGE_KEY_ACTIVE_MODEL = 'pf:activeModel';
const STORAGE_KEY_ACTIVE_MODEL_NAME = 'pf:activeModelName';

function createModeStore() {
	// Initialize from localStorage or defaults
	let initialMode: AppMode = 'explore';
	let initialActiveModel: number | null = null;
	let initialActiveModelName: string | null = null;

	if (typeof window !== 'undefined') {
		const storedMode = localStorage.getItem(STORAGE_KEY_MODE);
		const storedActiveModel = localStorage.getItem(STORAGE_KEY_ACTIVE_MODEL);
		const storedActiveModelName = localStorage.getItem(STORAGE_KEY_ACTIVE_MODEL_NAME);

		if (storedMode === 'model' || storedMode === 'explore') {
			initialMode = storedMode;
		}
		if (storedActiveModel) {
			const parsed = parseInt(storedActiveModel, 10);
			if (!isNaN(parsed)) {
				initialActiveModel = parsed;
			}
		}
		if (storedActiveModelName) {
			initialActiveModelName = storedActiveModelName;
		}
	}

	const { subscribe, set, update } = writable<ModeState>({
		mode: initialMode,
		activeModel: initialActiveModel,
		activeModelName: initialActiveModelName
	});

	// Subscribe to changes and persist to localStorage
	if (typeof window !== 'undefined') {
		subscribe((state) => {
			localStorage.setItem(STORAGE_KEY_MODE, state.mode);
			if (state.activeModel !== null) {
				localStorage.setItem(STORAGE_KEY_ACTIVE_MODEL, String(state.activeModel));
			} else {
				localStorage.removeItem(STORAGE_KEY_ACTIVE_MODEL);
			}
			if (state.activeModelName !== null) {
				localStorage.setItem(STORAGE_KEY_ACTIVE_MODEL_NAME, state.activeModelName);
			} else {
				localStorage.removeItem(STORAGE_KEY_ACTIVE_MODEL_NAME);
			}
		});
	}

	return {
		subscribe,
		setMode(mode: AppMode) {
			update((state) => ({ ...state, mode }));
		},
		setActiveModel(modelId: number | null, modelName: string | null = null) {
			update((state) => ({ ...state, activeModel: modelId, activeModelName: modelName }));
		},
		switchMode(mode: AppMode) {
			// Switching modes keeps the active model for potential re-selection
			set({ mode, activeModel: null, activeModelName: null });
		},
		reset() {
			set({ mode: 'explore', activeModel: null, activeModelName: null });
		}
	};
}

export const modeStore = createModeStore();
