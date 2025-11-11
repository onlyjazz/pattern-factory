import { writable } from "svelte/store";

export const fileHandle = writable<FileSystemFileHandle | null>(null);