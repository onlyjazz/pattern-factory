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
	async switchMode(mode: AppMode) {
		// When switching TO model mode, fetch active model from backend
		if (mode === 'model') {
			try {
				const response = await fetch('http://localhost:8000/active-model');
				if (response.ok) {
					const data = await response.json();
					if (data.model_id) {
						// Fetch model details to get the name
						const modelResponse = await fetch(`http://localhost:8000/models/${data.model_id}`);
						if (modelResponse.ok) {
							const modelData = await modelResponse.json();
							set({ mode, activeModel: data.model_id, activeModelName: modelData.name });
							return;
						}
					}
				}
			} catch (e) {
				console.error('Failed to fetch active model:', e);
			}
		}
		// When switching TO explore mode or if model fetch fails, clear model state
		set({ mode, activeModel: null, activeModelName: null });
	},
		reset() {
			set({ mode: 'explore', activeModel: null, activeModelName: null });
		}
	};
}

export const modeStore = createModeStore();
