import { json, error } from '@sveltejs/kit';
import type { RequestHandler } from '@sveltejs/kit';

const API_BASE = process.env.VITE_API_BASE || 'http://localhost:8000';

export const GET: RequestHandler = async ({ params }) => {
	const { id } = params;

	if (!id) {
		return error(400, 'Card ID is required');
	}

	try {
		const response = await fetch(`${API_BASE}/cards/${id}/story`);

		if (!response.ok) {
			return error(response.status, `Backend error: ${response.statusText}`);
		}

		const data = await response.json();
		return json(data);
	} catch (err) {
		const message = err instanceof Error ? err.message : 'Unknown error';
		return error(500, `Failed to fetch card story: ${message}`);
	}
};
