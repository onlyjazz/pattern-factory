// src/lib/chat/sessionStore.ts
import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export type Role = 'user' | 'assistant';
export type Message = {
  id: string;
  sessionId: string;
  sender: Role;
  text: string;
  tableData?: Array<Record<string, any>>;
  ts: number;
};

export type Session = {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
};

const SESS_KEY = 'chats:v1:sessions';
const MSGS_KEY = 'chats:v1:messages';
const CUR_KEY  = 'chats:v1:current';

// ---- Safe storage helpers (no-ops on server) -------------------------------
function read<T>(k: string, d: T): T {
  if (!browser) return d;
  try {
    const v = localStorage.getItem(k);
    return v ? (JSON.parse(v) as T) : d;
  } catch {
    return d;
  }
}

function write<T>(k: string, v: T): void {
  if (!browser) return;
  localStorage.setItem(k, JSON.stringify(v));
}

function readCurrentId(): string | null {
  if (!browser) return null;
  try {
    return localStorage.getItem(CUR_KEY);
  } catch {
    return null;
  }
}

// (kept if you use it elsewhere; also guarded)
function loadMessages(): Message[] {
  if (!browser) return [];
  const saved = localStorage.getItem('aiChat:messages:v1');
  return saved ? JSON.parse(saved) : [];
}

// ---- In-memory state --------------------------------------------------------
let _sessions: Session[] = read(SESS_KEY, []);
let _messages: Message[] = read(MSGS_KEY, []);
let _currentId: string | null = readCurrentId();

// Exposed stores (derived from in-memory state)
export const sessions = writable<Session[]>(_sessions.sort((a, b) => b.updatedAt - a.updatedAt));
export const currentSessionId = writable<string | null>(_currentId);
export const messages = writable<Message[]>(
  _currentId ? _messages.filter(m => m.sessionId === _currentId).sort((a, b) => a.ts - b.ts) : []
);

// ---- Utilities --------------------------------------------------------------
function persist() {
  write(SESS_KEY, _sessions);
  write(MSGS_KEY, _messages);

  const cur = _currentId;
  sessions.set([..._sessions].sort((a, b) => b.updatedAt - a.updatedAt));
  messages.set(
    cur ? _messages.filter(m => m.sessionId === cur).sort((a, b) => a.ts - b.ts) : []
  );
  currentSessionId.set(cur);
}

// ---- Public API -------------------------------------------------------------
export function ensureSession(): string {
  if (_currentId && _sessions.find(s => s.id === _currentId)) return _currentId;
  const s = createSession('New Chat');
  switchSession(s.id);
  return s.id;
}

export function createSession(title = 'New Chat'): Session {
  const now = Date.now();
  const s: Session = { id: crypto.randomUUID(), title, createdAt: now, updatedAt: now };
  _sessions.unshift(s);
  persist();
  return s;
}

export function renameSession(id: string, title: string) {
  const s = _sessions.find(x => x.id === id);
  if (s) {
    s.title = title;
    s.updatedAt = Date.now();
    persist();
  }
}

export function switchSession(id: string) {
  _currentId = id;
  if (browser) {
    try {
      localStorage.setItem(CUR_KEY, id);
    } catch {/* ignore */}
  }
  const s = _sessions.find(x => x.id === id);
  if (s) s.updatedAt = Date.now();
  persist();
}

export function deleteSession(id: string) {
  _sessions = _sessions.filter(s => s.id !== id);
  _messages = _messages.filter(m => m.sessionId !== id);

  if (_currentId === id) _currentId = _sessions[0]?.id ?? null;

  if (browser) {
    try {
      if (_currentId) localStorage.setItem(CUR_KEY, _currentId);
      else localStorage.removeItem(CUR_KEY);
    } catch {/* ignore */}
  }
  persist();
}

export function appendMessage(
  sender: Role,
  text: string,
  opts?: { tableData?: Array<Record<string, any>> }
): Message {
  if (!_currentId) ensureSession();
  const now = Date.now();
  const msg: Message = {
    id: crypto.randomUUID(),
    sessionId: _currentId!,
    sender,
    text,
    tableData: opts?.tableData,
    ts: now
  };
  _messages.push(msg);
  const s = _sessions.find(x => x.id === _currentId);
  if (s) s.updatedAt = now;
  persist();
  return msg;
}

export function updateMessageById(
  id: string,
  updates: Partial<Pick<Message, 'text' | 'tableData'>>
) {
  const idx = _messages.findIndex(m => m.id === id);
  if (idx >= 0) {
    _messages[idx] = { ..._messages[idx], ...updates };
    persist();
  }
}

export function getCurrentId(): string | null {
  return _currentId;
}
