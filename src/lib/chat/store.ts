import { writable } from "svelte/store";
import type { ResultTable } from './types';

const MSGS_KEY = 'chat:messages';
const TBLS_KEY = 'chat:tables';
const SID_KEY = 'chat:sessionId';

function read<T>(k: string, d: T): T {
    try { const v = localStorage.getItem(k); return v ? JSON.parse(v) as T : d; }
    catch { return d; }
}

function write<T>(k: string, v: T) { localStorage.setItem(k, JSON.stringify(v)); }

let sessionId = localStorage.getItem(SID_KEY) || crypto.randomUUID();
localStorage.setItem(SID_KEY, sessionId);

let _tables: ResultTable[] = read(TBLS_KEY, []);
export const tables = writable<ResultTable[](_tables.filter(t => t.sessionId === sessionId));
export const activeTableId = writable<string | null>(null);

function sync() {
    write(TBLS_KEY, _tables);
    const filtered = _tables.filter(t => t.sessionId === sessionId).sort((a,b)=>b.updatedAt-a.updatedAt);
    tables.set(filtered);
    if (filtered.length && !get(activeTableId)) activeTableId.set(filtered[0].id);
}

function get<T>(store: { subscribe: (run: (v:T)=>void)=>()=>void }): T {
    let val!: T;
    const unsub = store.subscribe(v=>val=v);
    unsub();
    return val;
}

export function logAssistantTable(args: { name: string; columns: string[]; rows: any[][]; sourceHash?: string }) {
    const now = Date.now();
    let t = _tables.find(x => x.sessionId === sessionId && (args.sourceHash ? x.sourceHash === args.sourceHash : x.name === args.name));
    if (t) {
        t.columns = args.columns;
        t.rows = args.rows;
        t.updatedAt = now;
    } else {
        t = { id: crypto.randomUUID(), sessionId, name: args.name, columns: args.columns, rows: args.rows, createdAt: now, updatedAt: now, sourceHash: args.sourceHash };
        _tables.unshift(t);
    }
    activeTableId.set(t.id);
    sync();
}

export function setActiveTable(id: string) { activeTableId.set(id); }
export function closeTable(id: string) { _tables = _tables.filter(t => t.id !== id); sync(); }