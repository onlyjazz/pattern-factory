/**
 * Centralized configuration for service endpoints.
 * Uses environment variables with sensible defaults for development.
 *
 * Environment Variables:
 * - VITE_API_BASE: HTTP API base URL (default: http://localhost:8000)
 * - VITE_WS_BASE: WebSocket base URL (default: ws://localhost:8000)
 * - VITE_FRONTEND_BASE: Frontend application base URL (default: http://localhost:5173)
 */

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
export const WS_BASE = import.meta.env.VITE_WS_BASE || 'ws://localhost:8000';
export const FRONTEND_BASE = import.meta.env.VITE_FRONTEND_BASE || 'http://localhost:5173';
