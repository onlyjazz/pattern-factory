import { writable } from "svelte/store";
import type { Pattern } from "./types";
import { API_BASE } from "$lib/config";

const url = `${API_BASE}/patterns`;
console.log("📡 FINAL URL →", url);

function createPatternsStore() {
    const { subscribe, set, update } = writable<Pattern[]>([]);

    return {
        subscribe,

        // --------------------------------------------------------
        // LOAD ALL PATTERNS
        // --------------------------------------------------------
        async refresh() {
            console.log("🔄 Refreshing patterns…");

            const res = await window.fetch(`${API_BASE}/patterns`);
            if (!res.ok) throw new Error("Failed to load patterns");

            const data = await res.json();
            console.log("📥 PATTERNS LOADED →", data);

            set(data);
        },

        // --------------------------------------------------------
        // ADD PATTERN
        // --------------------------------------------------------
        async addPattern(data: Pattern) {
            console.log("📤 RAW DATA →", data);
            console.log("📤 STRINGIFIED →", JSON.stringify(data));

            const res = await window.fetch(`${API_BASE}/patterns`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });

            if (!res.ok) {
                console.error("❌ Failed response adding pattern:", res.status);
                throw new Error("Failed to add pattern");
            }

            const created = await res.json();
            console.log("✅ PATTERN CREATED →", created);

            update((items) => [...items, created]);
        },

        // --------------------------------------------------------
        // UPDATE PATTERN
        // --------------------------------------------------------
        async updatePattern(id: number, data: Pattern) {
            console.log(`✏️ Updating pattern ${id}…`, data);

            const res = await window.fetch(`${API_BASE}/patterns/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            });

            if (!res.ok) throw new Error("Failed to update pattern");

            const updated = await res.json();
            console.log("✅ PATTERN UPDATED →", updated);

            update((items) =>
                items.map((p) => (p.id === id ? updated : p))
            );
        },

        // --------------------------------------------------------
        // DELETE PATTERN
        // --------------------------------------------------------
        async deletePattern(id: number) {
            console.log(`🗑️ Deleting pattern ${id}…`);

            const res = await window.fetch(`${API_BASE}/patterns/${id}`, {
                method: "DELETE"
            });

            if (!res.ok) throw new Error("Failed to delete pattern");

            update((items) => items.filter((p) => p.id !== id));
            console.log("🧹 PATTERN DELETED");
        }
    };
}

export const patterns = createPatternsStore();
export type { Pattern };
